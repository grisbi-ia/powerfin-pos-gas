# Cuadre de Caja — Ciclo de vida y consultas SQL

Documento de referencia para entender qué despachos y movimientos afectan el
efectivo al cerrar turno, y cómo consultarlo correctamente desde la base de datos.

## 1. Ciclo de vida del despacho

```
┌──────────────┐    completeDispatch    ┌──────────────┐    collectDispatch    ┌──────────────┐
│  AUTHORIZED  │ ──────────────────────► │  COMPLETED   │ ────────────────────► │  COLLECTED   │
│              │                         │              │                       │              │
│ shift_id = A │                         │ shift_id = A │                       │ shift_id = B │
│ total = 0    │                         │ total > 0    │                       │ total > 0    │
└──────┬───────┘                         └──────┬───────┘                       └──────────────┘
       │ cancelDispatch                         │ (cierre de turno sin cobrar)
       ▼                                        ▼
┌──────────────┐                    El despacho queda COMPLETED
│  CANCELLED   │                    en el shift A. Si otro cajero
│              │                    lo cobra en el shift B,
│ sri = NULL   │                    shift_id se SOBRESCRIBE a B.
└──────────────┘
```

### 1.1 AUTHORIZED — orden creada, surtidor no ha despachado

**Cuándo ocurre:**
- El despachador abre la venta en el POS, envía `PRESET` al Wayne.
- El cliente **no ha jalado el gatillo** todavía.
- O el cliente **se fue sin cargar** y el Wayne canceló por timeout interno
  (ATO=180s), pero FusionBridge no recibió/pudo enviar el evento de cancelación
  al backend.

**Efecto en el sistema:**
- La manguera queda **bloqueada**. No se puede autorizar otro despacho en esa
  manguera hasta cancelar manualmente el existente.
- `total = 0`, no tiene monto, no tiene IVA, no tiene pago.
- **No afecta el efectivo del cierre de turno.**

**Query para detectarlos:**
```sql
SELECT order_id, hose_id, created_at
FROM dispatches
WHERE shift_id = :shift_id AND status = 'AUTHORIZED';
```

### 1.2 COMPLETED — surtidor terminó, pendiente de cobro

**Cuándo ocurre:**
- El Wayne terminó de despachar. FusionBridge llamó a `POST /complete-dispatch`
  (o `POST /complete-by-pump`) con el monto y volumen reales.
- El backend calculó subtotal, IVA, total y actualizó `dispatch_details`.
- El cajero **aún no ha cobrado**. El despacho está en la cola de cobro del POS.

**Caso especial — Wayne AM=0:**
- El Wayne a veces reporta `amount=0` por una condición de carrera.
- El backend lo detecta (`total=0` + `status=COMPLETED`) y permite que la
  siguiente llamada a `completeDispatch` corrija los totales.
- Hasta que no tenga `total > 0`, `collectDispatch` lo rechaza con error:
  > "El despacho aún no tiene monto registrado."

**Efecto en el sistema:**
- Tiene monto, IVA, cliente, pero **no tiene pago registrado.**
- **No afecta el efectivo del cierre de turno.**
- Su `shift_id` es el del turno que lo **autorizó**, no el que lo cobre.

**Query para detectarlos:**
```sql
SELECT order_id, hose_id, total, created_at
FROM dispatches
WHERE shift_id = :shift_id AND status = 'COMPLETED';
```

### 1.3 COLLECTED — cobrado, cerrado

**Cuándo ocurre:**
- El cajero registró el pago mediante `POST /collect-dispatch`.
- Se crean registros en `dispatch_payments` (uno o varios, pago mixto).
- El `shift_id` se **sobrescribe** al turno del cajero que cobró:
  ```python
  dispatch.shift_id = body.collected_by_shift_id
  ```
  Esto significa que el efectivo pertenece al turno del **cobrador**, no al del
  autorizador.

**Efecto en el sistema:**
- **Este es el único estado que afecta el efectivo.**
- Los únicos despachos que entran en el cuadre de caja.

### 1.4 CANCELLED — cancelado

- Se canceló manualmente desde el POS (`POST /cancel`).
- `sri_status = NULL` — nunca debe llegar al SRI.
- **No cuenta en `dispatch_count` ni en efectivo.**

---

## 2. ¿Qué despachos entran en el cierre de turno?

### 2.1 dispatch_count (conteo total del turno)

El backend (`_compute_shift_summary`) cuenta:

```sql
SELECT COUNT(*)
FROM dispatches
WHERE shift_id = :shift_id
  AND status != 'CANCELLED';
```

**Incluye:** AUTHORIZED + COMPLETED + COLLECTED  
**Excluye:** CANCELLED

### 2.2 Ventas en efectivo — lo que DEBE estar en caja

```sql
SELECT COALESCE(SUM(dp.amount), 0) AS ventas_efectivo
FROM dispatches d
JOIN dispatch_payments dp ON dp.dispatch_id = d.dispatch_id
WHERE d.shift_id = :shift_id
  AND d.status = 'COLLECTED'
  AND dp.payment_method_id = 1;   -- 1 = CASH (usar ID, no code)
```

**Filtros obligatorios:**
| Filtro | Valor | Razón |
|--------|-------|-------|
| `d.status` | `'COLLECTED'` | Solo despachos cobrados tienen pago |
| `dp.payment_method_id` | `1` | Solo efectivo. Usar ID, no `pm.code = 'CASH'` (el código podría cambiar) |
| `d.shift_id` | `:shift_id` | El shift al que pertenece el efectivo (shift del cobrador) |

### 2.3 Ventas NO efectivo (tarjeta, crédito, transferencia, etc.)

```sql
SELECT pm.name, COUNT(DISTINCT d.dispatch_id) AS count,
       SUM(dp.amount) AS total
FROM dispatches d
JOIN dispatch_payments dp ON dp.dispatch_id = d.dispatch_id
JOIN payment_methods pm ON pm.payment_method_id = dp.payment_method_id
WHERE d.shift_id = :shift_id
  AND d.status = 'COLLECTED'
  AND dp.payment_method_id != 1
GROUP BY pm.name;
```

Estos montos **no son efectivo** y **no afectan el cuadre**. Son solo
informativos (para saber cuánto se vendió por otros medios).

---

## 3. Movimientos de caja que afectan el efectivo

Tabla `cash_movements`. Cada movimiento tiene un `type` y un `running_balance`.

### 3.1 Tipos y su efecto en el efectivo

| type | Efecto | Signo en fórmula | Descripción |
|------|--------|-----------------|-------------|
| `INCOME` | Suma | **+** | Ingreso extra de efectivo (ej. pago de deuda anterior) |
| `TRANSFER_IN` | Suma | **+** | Efectivo recibido de otro cajero |
| `EXPENSE` | Resta | **−** | Gasto o salida de caja (ej. compra de suministros) |
| `SAFE_DROP` | Resta | **−** | Envío de efectivo a caja fuerte |
| `TRANSFER_OUT` | Resta | **−** | Efectivo enviado a otro cajero |
| `DEPOSIT` | Resta | **−** | Depósito bancario |

### 3.2 Agrupación del backend

El backend (`_compute_shift_summary`) agrupa `INCOME + TRANSFER_IN` en un solo
rubro llamado `income`:

```python
income = await db.scalar(
    select(func.coalesce(func.sum(CashMovement.amount), 0))
    .where(CashMovement.shift_id == shift_id,
           CashMovement.type.in_(["INCOME", "TRANSFER_IN"]))
)
```

Los demás (`EXPENSE`, `DEPOSIT`, `TRANSFER_OUT`, `SAFE_DROP`) se consultan por
separado.

### 3.3 Query SQL equivalente

```sql
SELECT
    COALESCE(SUM(CASE WHEN type IN ('INCOME', 'TRANSFER_IN') THEN amount ELSE 0 END), 0) AS income,
    COALESCE(SUM(CASE WHEN type = 'EXPENSE'      THEN amount ELSE 0 END), 0) AS expense,
    COALESCE(SUM(CASE WHEN type = 'DEPOSIT'      THEN amount ELSE 0 END), 0) AS deposit,
    COALESCE(SUM(CASE WHEN type = 'TRANSFER_OUT' THEN amount ELSE 0 END), 0) AS transfer_out,
    COALESCE(SUM(CASE WHEN type = 'SAFE_DROP'    THEN amount ELSE 0 END), 0) AS safe_drop
FROM cash_movements
WHERE shift_id = :shift_id;
```

---

## 4. Fórmula completa del cuadre de caja

```
efectivo_esperado = opening_cash
                  + ventas_efectivo          (COLLECTED + payment_method_id = 1)
                  + income                   (INCOME + TRANSFER_IN)
                  − expense
                  − deposit
                  − transfer_out
                  − safe_drop

diferencia = closing_cash − efectivo_esperado

  diferencia > 0  →  SOBRANTE  (hay más efectivo del esperado)
  diferencia < 0  →  FALTANTE  (falta efectivo)
  diferencia = 0  →  CUADRADO
```

### 4.1 Query SQL completa

```sql
WITH
shift_base AS (
    SELECT shift_id, opening_cash, closing_cash, surplus, shortage, status
    FROM shifts WHERE shift_id = :shift_id
),
cash_sales AS (
    SELECT COALESCE(SUM(dp.amount), 0) AS total_cash
    FROM dispatches d
    JOIN dispatch_payments dp ON dp.dispatch_id = d.dispatch_id
    WHERE d.shift_id = :shift_id
      AND d.status = 'COLLECTED'
      AND dp.payment_method_id = 1
),
cash_mov AS (
    SELECT
        COALESCE(SUM(CASE WHEN type IN ('INCOME', 'TRANSFER_IN') THEN amount ELSE 0 END), 0) AS income,
        COALESCE(SUM(CASE WHEN type = 'EXPENSE'      THEN amount ELSE 0 END), 0) AS expense,
        COALESCE(SUM(CASE WHEN type = 'DEPOSIT'      THEN amount ELSE 0 END), 0) AS deposit,
        COALESCE(SUM(CASE WHEN type = 'TRANSFER_OUT' THEN amount ELSE 0 END), 0) AS transfer_out,
        COALESCE(SUM(CASE WHEN type = 'SAFE_DROP'    THEN amount ELSE 0 END), 0) AS safe_drop
    FROM cash_movements WHERE shift_id = :shift_id
)
SELECT
    sb.opening_cash                                                AS caja_inicial,
    cs.total_cash                                                  AS ventas_efectivo,
    cm.income                                                      AS income_transfer_in,
    cm.expense                                                     AS gastos,
    cm.deposit                                                     AS depositos,
    cm.transfer_out                                                AS transferencias_enviadas,
    cm.safe_drop                                                   AS envios_caja_fuerte,
    sb.opening_cash + cs.total_cash + cm.income
      - cm.expense - cm.deposit - cm.transfer_out - cm.safe_drop   AS efectivo_esperado,
    sb.closing_cash                                                AS efectivo_declarado,
    sb.closing_cash - (
        sb.opening_cash + cs.total_cash + cm.income
        - cm.expense - cm.deposit - cm.transfer_out - cm.safe_drop
    )                                                              AS diferencia,
    CASE
        WHEN sb.closing_cash - (sb.opening_cash + cs.total_cash + cm.income
            - cm.expense - cm.deposit - cm.transfer_out - cm.safe_drop) > 0
        THEN 'SOBRANTE'
        WHEN sb.closing_cash - (sb.opening_cash + cs.total_cash + cm.income
            - cm.expense - cm.deposit - cm.transfer_out - cm.safe_drop) < 0
        THEN 'FALTANTE'
        ELSE 'CUADRADO'
    END                                                            AS estado
FROM shift_base sb
CROSS JOIN cash_sales cs
CROSS JOIN cash_mov cm;
```

---

## 5. Tabla resumen: qué contribuye a qué

| Fuente | Tabla | Filtro clave | dispatch_count | Efectivo |
|--------|-------|-------------|:---:|:---:|
| Despachos AUTHORIZED | `dispatches` | `status = 'AUTHORIZED'` | ✅ | ❌ |
| Despachos COMPLETED | `dispatches` | `status = 'COMPLETED'` | ✅ | ❌ |
| Despachos COLLECTED (cash) | `dispatches` + `dispatch_payments` | `status = 'COLLECTED'` + `payment_method_id = 1` | ✅ | ✅ |
| Despachos COLLECTED (no cash) | `dispatches` + `dispatch_payments` | `status = 'COLLECTED'` + `payment_method_id != 1` | ✅ | ❌ |
| Despachos CANCELLED | `dispatches` | `status = 'CANCELLED'` | ❌ | ❌ |
| Cash movement INCOME | `cash_movements` | `type = 'INCOME'` | — | ✅ (+) |
| Cash movement TRANSFER_IN | `cash_movements` | `type = 'TRANSFER_IN'` | — | ✅ (+) |
| Cash movement EXPENSE | `cash_movements` | `type = 'EXPENSE'` | — | ✅ (−) |
| Cash movement DEPOSIT | `cash_movements` | `type = 'DEPOSIT'` | — | ✅ (−) |
| Cash movement TRANSFER_OUT | `cash_movements` | `type = 'TRANSFER_OUT'` | — | ✅ (−) |
| Cash movement SAFE_DROP | `cash_movements` | `type = 'SAFE_DROP'` | — | ✅ (−) |

---

## 6. Reglas importantes

1. **Usar `payment_method_id = 1`, NO `pm.code = 'CASH'`.** El ID es estable;
   el código podría renombrarse.

2. **El `shift_id` de un despacho COLLECTED es el del cobrador, no el del
   autorizador.** Si un despacho se autoriza en el turno 28 pero se cobra en el
   turno 29, el efectivo aparece en el turno 29.

3. **Los AUTHORIZED/COMPLETED no cobrados inflan el `dispatch_count` pero no el
   efectivo.** Al cerrar turno, espera ver más despachos que ventas en efectivo
   si hay pendientes de cobro.

4. **`INCOME` y `TRANSFER_IN` se suman en un solo rubro.** El backend los
   agrupa; las consultas SQL deben hacer lo mismo para que el cuadre coincida.

5. **Nunca contar CANCELLED.** No aportan al conteo, no aportan al efectivo,
   y su `sri_status` es NULL para evitar que lleguen al SRI.

---

## 7. Referencia rápida — script listo para usar

El script `scripts/ventas_turno.sql` contiene todas estas consultas listas para
ejecutar contra la base de datos:

```bash
psql -v shift_id=28 -f scripts/ventas_turno.sql
```

Incluye:
- Encabezado del turno
- Totales (dispatch_count, USD, IVA)
- Detalle de cada despacho con cliente, vehículo, forma de pago
- Totales por forma de pago
- Resumen por producto
- **Cuadre de caja completo** (efectivo esperado vs declarado)
- Desglose de movimientos de caja
- Desglose de transferencias
- Totales no-efectivo (referencia)
