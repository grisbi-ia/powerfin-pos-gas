# Flujos de Venta de Combustible — Powerfin POS

> **Documento de definición operativa.** Todos los escenarios posibles en una venta,
> verificados contra el código real, no contra el diseño.
>
> **Última actualización:** 2026-09-13 — **v0.38.0**
> **Verificado contra:** `pos/src/lib/components/SaleWizard.svelte`,
> `pos_backend/app/api/*.py`, `fusion-bridge/.../FusionMessageBuilder.java`,
> `pos/src/lib/components/DispenserCard.svelte`

---

## 0. Cambios vs versión anterior (2026-06-23)

Esta versión reemplaza la anterior, que describía el prototipo con ERP mock.
Diferencias **verificadas** (no cosméticas):

### 0.1 Eliminado (ya no existe en el sistema)

| Antes decía | Por qué se eliminó |
|---|---|
| Escenario 6 “Venta sin identificar (**Consumidor Final**)”, con `customer_id=FINAL` y opción “Sin identificar” en el paso 4 | Desapareció en Fase 7. Desde v0.37.3, `dispatch_types.requires_customer=true` para `SALE` y el backend responde **422** si falta el cliente. Documentarlo era inducir a un error de operación |
| Escenario 13 paso 4: “¿Desea cerrar igual con ventas pendientes de cobro?” | **Se bloquea** (v0.35.3): `409 — No puedes cerrar el turno: hay N despacho(s) pendiente(s) de cobro` |
| Escenario 20: “pendingOrders en memoria → se pierde / SOLUCIÓN: persistir en localStorage” | Ya está resuelto: `stores/pendingOrders.ts` persiste en localStorage y recarga |
| Escenario 15: “Supervisor fuerza cierre de turno ajeno” (**no implementado**) | Se mantiene documentado, pero **marcado como no implementado** (§5.21) |

### 0.2 Corregido (decía algo distinto a lo que hace el código)

| Antes decía | Ahora dice |
|---|---|
| Paso 3 del wizard: “selector de pistola” primero | El orden real es **placa → cliente → producto (pistola) → preset**. La pistola se elige *después* del cliente |
| `POST /collect` con `payment_method: "EFECTIVO"` | `payment_method_id: int` + `payments[]` (pago mixto) + `reference_code` |
| “**FusionBridge** responde 409 manguera ocupada” | El **409 lo emite el POS Backend** (`create_dispatch`, advisory lock por manguera) |
| “`POST /api/dispatch/authorize` a PowerFin” | El POS llama **directo a FusionBridge** (`POST /api/dispatch/authorize`) |
| “PowerFin responde **404 CUSTOMER_NOT_FOUND**” | El lookup responde **200 `{found:false}`**; y ahora **422** si el número es inválido o el registro dice que no existe |
| Escenario 12a: “reintenta automáticamente **3 veces**” | **No hay retry**: se muestra el mensaje real del backend |
| “Pendiente de Cobro = factura emitida” y factura en el paso 18 | **Timing fiscal real**: secuencial + clave se asignan al **crear**; el envío a Key49/SRI es **fire-and-forget al COBRAR** |
| Escenario 16: “mock VIP $1.100 / futuro precios por grado” | Los precios son **reales** por lista (`STANDARD`/`VIP`/…) × grado, desde `price_lists` / `price_list_items`. No se listan valores aquí: cambian |
| Escenario 17: crédito “al seleccionar forma de pago” | El crédito se resuelve **antes**: prompt “Contrato Disponible” en el paso de cliente + `dispatch_type_code=CREDIT` + `credit_contract_id` |
| Placa “máximo 10 caracteres” | `varchar(15)` y el input `maxlength="15"` |
| “Reimprimir desde historial (futuro)” | **Ya existe** (v0.35.6, respeta fecha/hora original) |
| Todo se atribuía a “PowerFin ERP” | Estos flujos los sirve el **POS Backend**; el ERP ya no está en el camino de la venta |

### 0.3 Agregado (el código ya lo tenía y no estaba documentado)

- **Regla 6 — Cliente e identificación obligatorios** (`SALE`), con el paso **4f** (§4.6).
- **Validación de cédula/RUC** (v0.38.0).
- **`plate_raw`**: la placa nunca se pierde aunque el vehículo no exista (v0.37.3).
- **Vehículo interno / venta por envase** (v0.23.0).
- **Pago mixto**.
- **Despachos en $0.00** y por qué se eliminó el auto-cancel (v0.19.4).
- **STOP durante FUELLING** con doble barrera anti-bolsillo.
- **Recuperación**: celular apagado / `PAY_IN` no eco-devuelto, `complete-by-pump`.
- **Transferencias de caja** (además de depósito a caja fuerte).
- **Medidores mecánicos** en apertura/cierre de turno.
- **Estados reales del dashboard** (incluye `STOPPED` y el estado “Cobrar”).
- **Crédito de sector público** con factura global (`PENDING_BULK_INVOICE`).

---

## 1. Arquitectura: quién hace qué

```
Powerfin POS (SvelteKit, tablet)
  │  UI + validaciones locales (espejo) + estado del wizard
  │
  ├──► POS Backend (FastAPI :8080)      ← /api/pos/*
  │      usuarios, turnos, clientes, despachos, caja, precios,
  │      contratos, secuenciales, clave de acceso, Key49/SRI
  │
  └──► FusionBridge (Quarkus :8090)     ← hardware
         una sola conexión TCP al Wayne Synergy (puerto 3011)
         impresión ESC/POS a printer_ip:9100
         eventos al POS por SSE
```

**Regla de oro:** el POS **no** habla con el dispensador ni imprime. Todo el hardware
pasa por FusionBridge. El POS **no** tiene base de datos propia: todo se persiste en el
POS Backend.

**Quién valida qué (defensa en profundidad):**

| Capa | Valida | Se puede evadir |
|---|---|---|
| POS (frontend) | Dígito verificador de cédula/RUC, campos requeridos, placa ≥ 3 | Sí (APK/PWA vieja) |
| POS Backend | Lo mismo **otra vez** + reglas de negocio (cliente obligatorio, cupo, estados) | **No** |
| Base de datos | `UNIQUE`, `CHECK`, `id_number NULL` = “no verificada” | **No** |

---

## 2. Reglas generales (aplican a todos los escenarios)

### Regla 1 — El que cobra es el dueño de la venta

El `shift_id` de una orden se define **al cobrar**, no al autorizar.

```
Juan autoriza  → orden con shift_id temporal de Juan
María cobra    → el backend sobrescribe shift_id al turno de María
El dinero va a la caja de quien cobró; cada uno cuadra SOLO lo que cobró.
```

```
POST /api/pos/dispatches/{order_id}/collect
{
  "collected_by_shift_id": 48,
  "payment_method_id": 1,
  "collected_amount": 42.50,
  "change_amount": 7.50,
  "reference_code": null,
  "payments": []                     ← lleno = pago mixto
}
```

### Regla 2 — “Pendiente de Cobro” lo ve y lo cobra cualquiera

Cuando el Wayne termina (pistola colgada), la manguera queda libre para otra venta y el
despacho pasa a **COMPLETED**. En el dashboard aparece como **🟢 Cobrar** para **todos**
los despachadores conectados. Cualquiera puede tocarlo y cobrar.

### Regla 3 — El despachador elige el preset: Monto o Galones

- **Por Monto** → `preset_type='MONEY'`, `TY=MONEY`, `VA=50.00`
- **Por Galones** → `preset_type='VOLUME'`, `TY=VOLUME`, `VA=10.00`
- **Llenar tanque** → `VA=FULL` (se envía como volumen)

### Regla 4 — No hace falta ver el progreso en tiempo real

El despachador autoriza y puede volver al dashboard. El dashboard refleja el estado en
vivo por SSE. No es necesario quedarse mirando la barra.

### Regla 5 — El layout físico viene del backend

Surtidores, lados y mangueras salen de `GET /api/pos/config`. **Nada está hardcodeado**,
tampoco las IPs de impresora (`dispensers.printer_ip` / `printer_port`) ni la política de
impresión (`system_config.printer_policy`).

### Regla 6 — Sin cliente con identificación válida **no hay venta** (v0.38.0)

Una factura electrónica necesita un receptor identificado, y Key49 **rechaza** las
cédulas con dígito verificador inválido (`Invalid identification for type 05`) y los RUC
que no existen en el SRI (`type 04`). Por eso:

- `SALE` exige cliente (v0.37.3) **y** que su identificación sea válida (v0.38.0).
- El bloqueo ocurre **antes** de que salga el combustible (`POST /dispatches` → 422) y se
  revalida **al cobrar** (`POST /collect` → 422).
- Un cliente sin identificación válida se queda con `id_number = NULL` y el POS muestra
  el paso **4f** para volver a pedirla. Ver §4.6.

### Regla 7 — Cuándo nace la factura

```
POST /dispatches        → consume el secuencial y calcula la clave de acceso (49 dígitos)
POST /collect           → dispara el envío a Key49/SRI (fire-and-forget)
                          + reconciler de fondo cada 120 s
```

**Antes de cobrar NO hay comprobante electrónico.** El dashboard no debe decir “factura
emitida” en Pendiente de Cobro.

---

## 3. Escenario 1 — Venta normal, datos completos

```
1.  El despachador ve el dashboard con todos los surtidores.
2.  Toca el Lado A del Surtidor 1 (estado: Disponible).

3.  PLACA — input de placa + Buscar.
    · Botón secundario: "🧉 Pedir Vehículo Interno" (venta por envase, §4.7).
    · Se exige mínimo 3 caracteres.

4.  El POS llama GET /api/pos/vehicles?plate=ABC1234.
    Respuesta: vehicle_found=true, incomplete_fields=[], dueño completo.

5.  CLIENTE — BillingConfirmation:
    "Juan Pérez — CED: 0912345675 — Lista VIP", correo y teléfono, y el precio ya
    actualizado a la lista del cliente.
    Botones: "✓ Correcto" · "Cambiar" · "✏️ Editar datos".
    (Si el cliente no tuviera identificación válida → paso 4f, §4.6.)

6.  El despachador presiona "✓ Correcto".

7.  PRODUCTO — "Seleccione el combustible": lista las pistolas del lado.
    Si el lado tiene 2+ pistolas, elige (Diesel/Súper/Extra).

8.  PRESET — elige tipo:
    "💵 Por Monto"  ·  "⛽ Por Galones".

9.  VALOR — input grande + botones rápidos ($5/$10/$20/$50/$100 o 1/2/5/10/20 gal)
    + "Llenar tanque". Estimación en vivo (monto ↔ galones con el precio unitario).

10. "Autorizar Despacho".
    Antes de enviar, el POS valida el cupo si es crédito de sector público.

11. POST /api/pos/dispatches
    · valida el estado de la manguera (advisory lock por hose_id)
    · valida cliente + identificación (422 si falta o es inválida)
    · consume el secuencial del punto de emisión del surtidor
    · calcula la clave de acceso (49 dígitos, módulo 11)
    · responde order_id = OV-20260913123456-789  (estado PENDING)
    Valida también el 409 "ya hay un despacho en curso en este dispensador".

12. POST /api/dispatch/authorize  →  FusionBridge (:8090)
    REQ_PUMP_PRESET_ID_001 con:
      HO=1@3.103  TY=MONEY  VA=50.00
      PAY_IN=OV=OV-…-789~CLI=0912345675~PLC=ABC1234~LISTA=VIP
    FusionBridge responde PRESET_SENT.

13. El wizard muestra "✅ Autorizado. Puede volver al inicio."
    Dashboard: Lado A → 🟡 Autorizado.

14. El despachador vuelve al dashboard y atiende otros clientes.

15. El cliente levanta la pistola, carga y cuelga.

16. El Wayne emite EVT_PUMP_NEW_TRANSACTION:
    SA=185  VO=42.500  AM=42.50  PU=3.103  PR=50.00

17. FusionBridge hace el handshake (Lock → ClearSale → Unlock) y llama
    POST /api/pos/dispatches/{order}/complete (o /complete-by-pump).
    El backend calcula subtotal, IVA (según tax_types del producto) y total.

18. SSE SALE_COMPLETED → el dashboard cambia el Lado A a:
    🟢 "Cobrar — $42.50 — Inició: Juan".
    La manguera ya está libre para otra venta.

19. CUALQUIER despachador puede tocar ("Cobrar"). Si es María, el wizard entra en
    modo collect y muestra el resumen del despacho.

20. RESUMEN — Total $42.50 · Volumen 42.500 gal · Preset $50.00 · Vuelto $7.50 ·
    Cliente y placa.
    Aquí también se puede "Cambiar" el facturador (§4.5).

21. María elige forma de pago (de `payment_methods`; algunas exigen referencia).

22. "Confirmar — Cobrar $42.50" (modal de confirmación).

23. POST /api/pos/dispatches/{order}/collect
    · el backend revalida: estado COMPLETED, monto > $0.00, identificación válida
    · sobrescribe shift_id al turno de María
    · registra los pagos
    · dispara en background el envío a Key49/SRI (Regla 7)

24. Política de impresión (desde system_config.printer_policy):
    ALWAYS (automático) · ASK (pregunta) · NEVER (no imprime).
    La impresión la ejecuta FusionBridge por TCP a printer_ip:9100.

25. "✅ Venta completada" → "Nueva Venta" → dashboard.
```

---

## 4. Variantes del paso CLIENTE

### 4.1 — 4a. Datos completos

Lo del Escenario 1, pasos 5–6. El precio se resuelve con
`GET /api/pos/prices?customerId=…&gradeId=…` cuando la lista del cliente no es STANDARD.

### 4.2 — 4b. Datos incompletos (falta correo, teléfono o dirección)

```
5.  Respuesta: incomplete_fields=["email"]  (o phone/address).
6.  CustomerForm (modo incomplete): identificación precargada y NO editable;
    pide los campos faltantes.
7.  "Continuar" → POST /api/pos/customers (actualiza el cliente y liga la placa).
8.  Vuelve a BillingConfirmation y sigue el flujo normal.
```

Variante: "Cancelar" → vuelve al paso de placa.

### 4.3 — 4c. Placa no encontrada, la persona facturadora SÍ existe

```
5.  Respuesta: vehicle_found=false.
6.  El wizard muestra "❌ Vehículo no encontrado" y pide la identificación
    (pestañas "Por Cédula/RUC" y "Por Nombre").
7.  El POS valida el dígito verificador ANTES de llamar; si está mal, muestra el
    motivo en pantalla y no busca.
8.  GET /api/pos/persons/lookup?id_type=CED&id_number=… → cliente encontrado.
9.  BillingConfirmation → sigue el flujo normal.
```

### 4.4 — 4d. Placa no encontrada y la persona NO existe (registro nuevo)

```
8.  Lookup responde {found:false}. Se avisa si el proveedor está caído:
    "⚠ No se pudo verificar automáticamente (Sercobaco/SRI). Confirme los datos."
9.  CustomerForm (registro): identificación (readonly, ya validada), nombre,
    correo (obligatorio), teléfono, dirección.
10. POST /api/pos/customers → valida identificación (422 si el dígito está mal;
    no se guarda).
11. BillingConfirmation → flujo normal.
```

Si el **registro del SRI responde que el RUC no existe**, el registro se rechaza
(**422**): ese documento jamás se podría facturar.

### 4.5 — 4e. Cambio de persona facturadora

```
1.  En BillingConfirmation (o en el resumen del cobro) → "Cambiar".
2.  Búsqueda por identificación o por nombre, con la misma validación.
3.  POST /api/pos/dispatches/{order}/billing  {customer_id, person_id, customer_name}
    → el backend revalida la identificación del nuevo facturador (422).
4.  El precio se recalcula con la lista del nuevo cliente.
```

### 4.6 — 4f. Identificación requerida  ⟵ NUEVO v0.38.0

**Cuándo aparece:** el cliente ya está registrado, pero su cédula/RUC es inválida o fue
**borrada** (`id_number = NULL`) porque con ella Key49 rechazaba la factura.

```
BillingConfirmation
  ⛔ Falta la identificación del cliente
     "Sin una cédula/RUC válido no se puede emitir la factura.
      Pídala al cliente e ingrésela aquí."
  [ 🪪 Ingresar identificación ]      ← único camino
  ("✓ Correcto" deshabilitado · "Editar datos" oculto)

4f. Ingresar identificación
    [Cédula] [RUC]        ← tipo preseleccionado
    ____________          ← validación en vivo, mismo mensaje que el backend
    [Cancelar] [Guardar]
        ↓ PUT /api/pos/persons/{person_id}  {id_type, id_number}
    200 → vuelve a BillingConfirmation con el dato bueno y la venta continúa
    422 → dígito verificador inválido (mensaje del backend tal cual)
    409 → ese número ya está registrado a nombre de otra persona
```

**Reglas del paso:**
- Necesita `person_id` (el POS lo obtiene del lookup). Si no lo tiene, indica usar
  "Cambiar" (§4.5).
- "Cancelar" vuelve a la confirmación, sin guardar.
- El POS **no** consulta el registro del SRI: eso es del backend.

**Qué significa “identificación inválida”** (validado contra producción):

| Tipo | Regla | ¿Bloquea? |
|---|---|---|
| Cédula | módulo 10 (provincia 01–24 y 30) | **Sí** — es exactamente lo que aplica Key49 |
| RUC persona natural (3er dígito 0–5) | cédula módulo 10 + `001` | **Sí** |
| RUC jurídica (9) / pública (6) | **solo estructura** | **No** por dígito verificador: el módulo 11 del RUC no es confiable (el registro del SRI tiene RUC que lo fallan y facturan normal). La existencia la confirma el SRI |
| Cualquiera | existencia en el registro (broker del SRI) | **Sí** — “no existe” bloquea; “proveedor caído” solo avisa |

### 4.7 — 4g. Vehículo interno (venta por envase)

Cuando el cliente no trae vehículo:

```
3.  "🧉 Pedir Vehículo Interno" → GET /api/pos/vehicles/predefined/next
    Devuelve el vehículo interno con MENOS despachos del día (balanceo de carga).
    Llena la placa automáticamente y el despachador presiona Buscar.
```

---

## 5. Escenarios

### 5.1 — Dos vehículos simultáneos en el mismo surtidor

Lados A y B son independientes: cada uno tiene su manguera, su estado y su orden. Los dos
pueden estar `AUTHORIZED`/`FUELLING` a la vez. Cada uno se cobra por separado, y el dinero
va a la caja de quien cobre cada uno (Regla 1).

### 5.2 — Un despachador con varias ventas en secuencia

Autoriza en Surtidor 1-Lado A, vuelve al dashboard, autoriza en Surtidor 2-Lado B. Cada
lado evoluciona por su cuenta. Puede cobrarlas en el orden que quiera, o que otro las cobre.

### 5.3 — Manguera ocupada (409)

```
1.  Carlos abre el wizard en Lado A.
2.  María (otra tablet) abre el mismo Lado A y autoriza primero.
3.  Carlos llega a "Autorizar Despacho".
4.  POST /api/pos/dispatches → 409
    "Este dispensador ya tiene un despacho en curso. Cobre o cancele el
     despacho existente antes de autorizar uno nuevo."
5.  El POS muestra ese mensaje (el `detail` real del backend).
6.  Carlos elige otro lado disponible.
```

> Nota: el 409 nace en el **POS Backend**, con un lock por `hose_id`. No lo emite
> FusionBridge, y el POS ya no traduce todos los 409 al mismo texto.

### 5.4 — Cancelar un preset antes de cargar

```
1.  El despacho está AUTHORIZED (el cliente aún no jaló la pistola).
2.  El despachador toca el lado en el dashboard → "Cancelar preset".
3.  POST /api/dispatch/cancel a FusionBridge → REQ_PUMP_CLEAR_PRESET_ID_xxx → IDLE.
4.  POST /api/pos/dispatches/{order}/cancel → CANCELLED, sin SRI.
5.  Dashboard: 🟢 Disponible.
```

Límites del cancel (backend):
- `COLLECTED` → **409** (ya cobrado, no se cancela).
- `COMPLETED` con `total > 0` → **409** (ya salió combustible).
- `AUTHORIZED`, o `COMPLETED` con `total = 0` → permitido.

### 5.5 — STOP durante el despacho (doble barrera anti-bolsillo)

Mientras la manguera está en `FUELLING`, el POS ofrece detener el despacho. Para evitar
cortes accidentales hay **doble barrera**: un botón grande y seguro + una acción pequeña y
deliberada de confirmación. Al detener:

```
1.  POST /api/dispatch/stop a FusionBridge.
2.  Se espera ~2 s y se envía REQ_PUMP_CLEAR_STOP_ID_xxx.
3.  Antes de un nuevo PRESET también se manda REQ_PUMP_CLEAR_STOP_ID_xxx.
    (El Wayne Synergy queda limpio y no arrastra el STOP anterior.)
```

### 5.6 — Despacho en $0.00 (carrera `AM=0`)

El Wayne a veces reporta `amount=0` por una condición de carrera al terminar.

- El backend detecta `total=0` + `COMPLETED` y **permite** que la siguiente llamada de
  `completeDispatch` corrija los totales.
- `collect` **rechaza** el cobro mientras el total sea $0.00:
  `"El despacho aún no tiene monto registrado. Espere a que el surtidor termine."`
- Un `COMPLETED` con `total=0` **sí** se puede cancelar (nunca salió combustible).

**No hay auto-cancel**: el `ATO=180s` del propio Wayne cierra el preset huérfano; el
sistema ya no lo duplica.

### 5.7 — Celular apagado / `PAY_IN` no eco-devuelto (recuperación)

El Wayne no siempre devuelve el `PAY_IN` en los flujos de PRESET.

```
1.  La venta terminó en el Wayne, pero FusionBridge no pudo casarla por PAY_IN.
2.  FusionBridge cae al fallback por bomba + manguera
    (POST /api/pos/dispatches/complete-by-pump), con reintentos.
3.  El POS detecta el pendiente en cuanto la manguera pasa a IDLE aunque la orden
    local siga en FUELLING, y muestra "Cobrar".
4.  Al reconectar, FusionBridge consulta REQ_GET_PUMP_SALES y casa las ventas
    ocurridas offline; el dashboard se actualiza por SSE.
```

### 5.8 — Impresora no disponible

```
1.  La venta está cobrada; se solicita el ticket.
2.  La impresora (dispensers.printer_ip:printer_port) no responde.
3.  FusionBridge devuelve un error claro:
    "Printer not reachable: <ip>:<port>".
4.  El wizard muestra "⚠ Error al imprimir" con "Reintentar".
5.  El despachador puede reintentar o continuar: el cobro ya está registrado.
6.  El ticket se puede reimprimir después desde el historial
    (respeta la fecha y hora originales del despacho).
```

**El error de impresión NUNCA bloquea ni revierte la venta.**

### 5.9 — POS Backend o FusionBridge no disponibles

**5.9a — POS Backend caído al crear la orden**

```
· POST /api/pos/dispatches falla (sin conexión).
· El wizard muestra el error real; no hay reintento automático.
· Nada se persistió: el despachador reintenta o vuelve al dashboard.
```

**5.9b — FusionBridge caído al autorizar**

```
· La orden SÍ existe en el POS Backend (quedó PENDING, la manguera no recibió preset).
· El POS avisa que no hay conexión con los surtidores; la orden queda pendiente.
· El banner de "Sin conexión con FusionBridge — reconectando…" aparece en el POS.
· Al reconectar, el estado se reconstruye por SSE + el recovery (§5.7).
```

### 5.10 — Cliente VIP vs STANDARD

El precio se determina por **lista del cliente × grado**, y la fuente de verdad es el
POS Backend (`price_lists` / `price_list_items`):

```
GET /api/pos/prices?customerId=<identificación>&gradeId=<grado>&vehicleId=<opcional>
```

La lista puede venir del vehículo (prioridad), del cliente, o ser `STANDARD`. El POS
nunca calcula precios por su cuenta.

### 5.11 — Crédito privado (contrato con cupo)

```
1.  El paso CLIENTE detecta que el vehículo tiene contrato de crédito vigente y
    muestra: "Contrato Disponible: <código>" con el cupo por producto.
2.  "Sí, usar crédito" → la venta se autoriza con dispatch_type_code=CREDIT y
    credit_contract_id.
3.  POST /api/pos/dispatches valida el cupo (validate_credit_dispatch).
    Si el monto excede el cupo → error explícito con el disponible.
4.  La venta queda PENDING_PAYMENT y se cobra contra el contrato.
```

### 5.12 — Crédito de sector público (facturación global)

Contratos `NO_INDEFINIDO` (municipios, GAD, etc.):

```
1.  Igual que 5.11, pero la venta NO consume secuencial al autorizar.
2.  Cada despacho se marca credit_status=PENDING_BULK_INVOICE.
3.  Al liquidar el período:
    · GET  /api/pos/dispatches/pending-bulk
    · POST /api/pos/dispatches/bulk-invoice   (consume UN secuencial y emite
      una factura global con un ítem por despacho)
    · los despachos pasan a INVOICED
4.  El ticket de crédito se imprime con la firma del cliente y el código de contrato.
```

### 5.13 — Validaciones de placa

```
a. Menos de 3 caracteres → "Buscar" deshabilitado.
b. "abc-1234" → se normaliza a "ABC1234" (mayúsculas, sin espacios ni guiones).
c. Solo números ("1234") → permitido.
d. Caracteres especiales → se limpian.
e. Máximo 15 caracteres (columna varchar(15)).
f. Si el vehículo no está registrado:
   · la placa se guarda igual en dispatches.plate_raw (no se pierde nunca);
   · si el cliente se identifica, el vehículo se crea y queda ligado a él.
```

### 5.14 — Preset: Monto vs Galones

Ver Regla 3. El tipo elegido determina `preset_type` en la orden, `TY` en el comando al
Wayne y qué campo ve el despachador. "Llenar tanque" envía `VA=FULL`.

### 5.15 — Recarga de página durante una venta

```
1.  El despachador recarga la página (F5) o se queda sin batería.
2.  Al volver: se restaura el token, el turno abierto y las órdenes pendientes
    (pendingOrders se persiste en localStorage).
3.  El estado de las mangueras se reconstruye por SSE.
4.  Si la venta ya terminó, el pendiente sigue ahí y se puede cobrar.
```

### 5.16 — Varios despachadores mirando el mismo surtidor

Todos ven el mismo estado por SSE. El primero que autoriza gana; el segundo recibe
**409** (§5.3). Si la venta ya está en “Cobrar”, cualquiera puede cobrarla.

### 5.17 — A autoriza, B cobra

Ver Regla 1. Al cobrar, el `shift_id` se sobrescribe al de B y el dinero entra a la caja
de B. En el cuadre, la venta aparece **solo** en el turno de B; A no la ve.

### 5.18 — Varias ventas pendientes de cobro a la vez

El dashboard muestra cada lado con su monto. Distintos despachadores pueden cobrar
distintos lados en paralelo; cada venta cae en el turno de quien la cobró.

### 5.19 — Cierre de turno

```
1.  El despachador presiona "Cerrar turno".
2.  GUARD (v0.35.3): si hay despachos COMPLETED sin cobrar →
    409 "No puedes cerrar el turno: hay N despacho(s) pendiente(s) de cobro.
         Cobra o cancela todos los despachos antes de cerrar."
    (No hay opción de "cerrar igual".)
3.  Si hay despachos AUTHORIZED (no despachados), también se avisa/bloquea.
4.  Medidores mecánicos: se registran las lecturas de cierre
    (GET/PUT /api/pos/shifts/{id}/meter-readings) cuando aplica.
5.  El POS muestra el resumen:
      efectivo esperado = apertura + cobros en efectivo + TRANSFER_IN
                          − DEPOSIT − SAFE_DROP − TRANSFER_OUT
   (ver §5.20 y §5.21)
6.  El despachador ingresa el efectivo contado.
7.  El POS calcula y muestra sobrante/faltante.
8.  POST /api/pos/shifts/{id}/close → turno CLOSED.
9.  El comprobante de cierre se puede reimprimir después
    (GET /api/pos/shifts/{id}/receipt-data).
```

### 5.20 — Depósito a caja fuerte

```
1.  El dashboard alerta cuando el efectivo acumulado pasa el máximo
    (system_config.max_cash_in_hand).
2.  Caja → "Depositar": monto + motivo.
3.  POST /api/pos/cash-movements (tipo SAFE_DROP).
4.  El efectivo de la caja del turno baja; el cierre ya lo descuenta.
```

### 5.21 — Transferencia de caja entre despachadores

```
POST /api/pos/transfers
  → genera TRANSFER_OUT en el turno de origen y TRANSFER_IN en el de destino
```

Es un movimiento **distinto** del depósito a caja fuerte y se refleja en el cuadre de
ambos turnos. `GET /api/pos/users/online` lista quién está conectado (a quién se le puede
transferir).

### 5.22 — Cierre forzado de turno ajeno — ⚠️ NO IMPLEMENTADO

**No existe** endpoint de cierre forzado en el POS Backend. Se deja documentado como
requisito pendiente: hoy un turno abierto de un despachador ausente solo se puede cerrar
desde el turno de ese usuario. Si se implementa, debe quedar con auditoría (quién, cuándo,
por qué) y registrar la diferencia como cierre forzado.

---

## 6. Estados del dashboard por manguera (reales)

Del código (`DispenserCard.svelte`):

| Estado | Color | Significado | Al tocar |
|---|---|---|---|
| `IDLE` — Disponible | 🟢 Verde | Libre para vender | Iniciar wizard |
| `CALLING` — Llamando | 🔵 Azul | Levantaron la pistola sin autorizar | Ver estado |
| `AUTHORIZED` — Autorizado | 🟡 Amarillo | Preset enviado, esperando la pistola | Ver detalle / Cancelar preset |
| `STARTING` — Iniciando | — | Arrancando el despacho | Ver estado |
| `FUELLING` — Despachando | 🟠 Naranja | Cargando | Ver progreso / STOP |
| `PAUSED` — Pausado | 🟣 Morado | Despacho pausado | Ver estado |
| `STOPPED` — Detenido | — | Detenido por el despachador | Ver estado |
| **Cobrar** (pendiente) | 🟢 Verde | Venta terminada, **sin cobrar** | Cobrar (cualquiera) |
| `CLOSED` — Cerrado | 🔴 Rojo | Surtidor fuera de servicio | No disponible |
| `ERROR` — Error | 🔴 Rojo | Error del surtidor | No disponible |

> “Cobrar” **no** implica factura emitida: el comprobante se envía al cobrar (Regla 7).

---

## 7. Pasos del wizard (reales)

```
1.  PLACA                 → input + Buscar (o "Pedir Vehículo Interno")
2.  CLIENTE
    2a. DATOS COMPLETOS   → BillingConfirmation: ✓ Correcto / Cambiar / Editar
    2b. DATOS INCOMPLETOS → CustomerForm (email/teléfono/dirección)
    2c. PLACA NO ENCONTRADA → búsqueda por cédula/RUC o por nombre
    2d. ID NO ENCONTRADO  → CustomerForm (registro nuevo)
    2e. IDENTIFICACIÓN REQUERIDA → 🪪 re-captura (v0.38.0)
    2f. CAMBIAR FACTURADOR → búsqueda de otra persona
3.  PRODUCTO              → selección de pistola / combustible
4.  TIPO DE PRESET        → Por Monto | Por Galones
5.  VALOR                 → monto o galones (+ Llenar tanque)
6.  AUTORIZAR             → POST /dispatches + PRESET al FusionBridge
7.  DASHBOARD             → el despachador puede atender otros clientes
8.  DESPACHO              → el dashboard refleja el estado en vivo
9.  COBRAR                → cualquier despachador, modo collect:
                            RESUMEN → PAGO → CONFIRMAR
10. IMPRIMIR              → según printer_policy (ALWAYS/ASK/NEVER)
11. NUEVA VENTA           → volver al dashboard
```

---

## 8. Errores frecuentes → qué ve el despachador

| Situación | Respuesta | Mensaje / efecto |
|---|---|---|
| Cédula con dígito verificador inválido | 422 | "La cédula no es válida (dígito verificador incorrecto). Vuelva a pedir el número al cliente." |
| RUC que el SRI no conoce | 422 | "No existe en el registro… no se puede facturar con una identificación inexistente." |
| Proveedor de identidad caído | 200 + aviso | "⚠ No se pudo verificar automáticamente (Sercobaco/SRI). Confirme los datos." |
| `SALE` sin cliente | 422 | "Este tipo de despacho requiere cliente: registre la identificación o busque una placa con dueño." |
| Cliente sin identificación (`id_number NULL`) | 422 | "El cliente X no tiene identificación registrada. Pida la cédula (o RUC)…" |
| Identificación nueva ya registrada a otro nombre | 409 | "La identificación … ya está registrada a nombre de …" |
| Manguera con despacho en curso | 409 | "Este dispensador ya tiene un despacho en curso…" |
| Intento de cobrar en $0.00 | 409 | "El despacho aún no tiene monto registrado…" |
| Cancelar algo ya cobrado o con combustible | 409 | "No se puede cancelar un despacho ya cobrado / con combustible despachado." |
| Cerrar turno con pendientes de cobro | 409 | "No puedes cerrar el turno: hay N despacho(s) pendiente(s) de cobro." |
| Impresora inalcanzable | error visible | "⚠ Error al imprimir" + Reintentar (la venta no se pierde) |

---

## 9. Endpoints que usa el POS

```
Auth / config
  POST /api/pos/auth/login                      GET  /api/pos/config
  GET  /api/pos/station-info                    GET  /api/pos/users/online

Cliente
  GET  /api/pos/vehicles?plate=…                GET  /api/pos/vehicles/predefined/next
  PUT  /api/pos/vehicles/{id}/billing-person
  GET  /api/pos/customers?q=…                   GET  /api/pos/customers/by-id
  POST /api/pos/customers
  GET  /api/pos/persons/lookup                  PUT  /api/pos/persons/{id}   ← re-captura de identificación
  GET  /api/pos/prices                          GET  /api/pos/credit-contracts/{id}/available

Despacho
  POST /api/pos/dispatches                      POST /api/pos/dispatches/{order}/complete
  POST /api/pos/dispatches/complete-by-pump     POST /api/pos/dispatches/{order}/collect
  POST /api/pos/dispatches/{order}/cancel       POST /api/pos/dispatches/{order}/billing
  GET  /api/pos/dispatches/active               GET  /api/pos/dispatches/{order}/sri-status
  GET  /api/pos/dispatches/pending-bulk         POST /api/pos/dispatches/bulk-invoice

Caja y turno
  POST /api/pos/shifts/open                     GET  /api/pos/shifts/current
  POST /api/pos/shifts/{id}/close               GET  /api/pos/shifts/{id}/receipt-data
  GET/PUT /api/pos/shifts/{id}/meter-readings   GET  /api/pos/shifts/{id}/dispatches
  GET  /api/pos/shifts/{id}/cash-summary        POST /api/pos/cash-movements
  POST /api/pos/transfers

Hardware (FusionBridge, otro puerto)
  POST /api/dispatch/authorize      POST /api/dispatch/cancel
  POST /api/dispatch/stop           POST /api/dispatch/payment-lock|clear|unlock
```

---

## 10. Pendientes conocidos (declarados, no implementados)

- **Cierre forzado de turno** por supervisor (§5.22).
- **Prueba E2E formal** admin → POS.
- **Rate limiting** en el login (Nginx).
- Reproceso masivo de facturas de otros días (hoy el reenvío con fecha de hoy es caso por
  caso y es una decisión fiscal).
- Mover la URL/token del servicio de identidad a `system_config` (hoy están en código) —
  ver `CODE_REVIEW_FINDINGS.md`.

---

## Anexo — Glosario de estados del despacho (base de datos)

| Estado | Significado |
|---|---|
| `PENDING` | Orden creada, el preset podría no haberse enviado aún |
| `AUTHORIZED` | Preset enviado, el cliente no ha cargado. **Bloquea la manguera** |
| `COMPLETED` | El surtidor terminó; pendiente de cobro |
| `COLLECTED` | Cobrado; el dinero pertenece al turno que cobró |
| `CANCELLED` | Cancelado; **nunca** va al SRI (`sri_status = NULL`) |

`credit_status`: `PENDING_PAYMENT` · `PENDING_BULK_INVOICE` · `INVOICED`

`sri_status`: `PENDING` → `CREATED`/`SIGNED`/`SENT`/`RECEIVED` → `AUTHORIZED`/`NOTIFIED`,
o `REJECTED`/`FAILED`. Un estado no final se reconcilia contra Key49 cada 120 s.
