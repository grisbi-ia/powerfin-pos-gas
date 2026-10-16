# Incidente SRI/Key49 — Facturas del emisor anterior emitidas por NEOGUAYAS

> **Estado:** investigado, verificado contra el SRI y **consolidado el 2026-09-25**.
> Caso **22294 corregido**. Pendiente: reversar 233 facturas, reemitir 154 ventas
> de NEOGUAYAS y resolver 69 ventas del emisor anterior.
> **No ejecutar acciones masivas sin autorización.** Este documento reemplaza las
> revisiones anteriores; el detalle completo está en el CSV referenciado.

## 1. Contexto: hay DOS emisores en el histórico

En el cambio de dueño/vendedor del combustible (2026-08-04/05) cambiaron el
establecimiento y el punto de emisión, y **los secuenciales se resetearon a 1**:

| Emisor | RUC | Serie | Vigencia | Ventas |
|---|---|---|---|---|
| **ANTERIOR** | `0190379760001` | `001-40x` | hasta 2026-08-04 | 12.174 |
| **NUEVO** (NEOGUAYAS SA) | `0993230839001` | `003-50x` | desde 2026-08-05 | ~11.900 |

Las facturas del emisor anterior **no se borraron** (se mantiene el historial) y
debían emitirse en **su** tenant Key49 con **su** RUC y **su** fecha. La app solo
tiene configurado al **emisor nuevo** (`company_info` + `key49_api_key`), y **no
soporta multi-emisor**.

> Las facturas del emisor anterior están en **otro tenant Key49**: al consultar
> `GET /invoices/<id>` de una factura `0190379760001` con la clave actual, Key49
> responde **404 `DOCUMENT_NOT_FOUND`**.

## 2. Causa raíz

**A. Re-clavado con el emisor equivocado.**
La recuperación masiva del **11/09/2026** (cierre del incidente PLAN_EXPIRED,
`recover_pending_invoices.py`) tomó ventas del **emisor anterior** que estaban
`PENDING` y les regeneró la clave con el `company_info` **actual** (RUC
`0993230839001`) y el punto de emisión **actual** (`003-50x`). Es decir, les puso
el **RUC y la serie del emisor nuevo**, en vez del RUC anterior y su fecha.

- `pos_backend/scripts/recover_pending_invoices.py` → `_regen_access_key()`
- `pos_backend/app/services/key49_service.py` → `_refresh_access_key_for_today()`

**B. Linkeo 409 sin verificación.**
`pos_backend/app/services/key49_service.py` → `emitir_factura()` (rama
`409 duplicate`): copia `error.existing_document` al despacho **sin comparar
receptor, total ni número**. Como las ventas viejas ocuparon números `003-50x` de
la serie nueva, cuando una venta nueva consumió el mismo número el POS linkeó la
factura ajena en silencio.

**C. Sin constraint.** `dispatches.key49_invoice_id` / `key49_access_key` sin
`UNIQUE`.

## 3. Verificación contra el SRI — NO hay duplicado

Comprobado con lecturas (`GET`) a Key49:

- Para cada venta nueva que comparte número, `GET /invoices?access_key=<clave
  propia>`: **164/175 no tienen factura propia** (no existe otro documento).
- Para las 254, `GET /invoices/<id>` y comparación `recipient.id` + monto.

**Hay UN solo documento por número** (establishment + issue_point +
sequence_number). El mismo `003-501-XXXX` aparece en **dos filas de `dispatches`**,
pero en el SRI es **una sola factura**. No es "facturación duplicada"; es
**emisor equivocado**: NEOGUAYAS figura como emisor de ventas que no fueron suyas.

## 4. Resultado final y acciones

Detalle completo en `docs/incidente_sri_2026-09-11_desglose.csv` (323 filas;
columna `accion`).

| `accion` | Casos | Monto | Qué significa |
|---|---|---|---|
| **`REVERSAR`** | **233** | base $2.658,58 · IVA $398,50 · **total $3.057,08** | Factura emitida por NEOGUAYAS para un cliente del emisor anterior → **reversar con nota de crédito** |
| **`CONSERVAR`** | 21 | — | La factura de NEOGUAYAS **sí corresponde** a una venta de NEOGUAYAS → **no reversar**; solo desvincular el despacho viejo que apunta a ella |
| **`FACTURAR_RUC_ANTERIOR`** | 69 | $1.245,76 | Venta del emisor anterior `COLLECTED` sin facturar → facturar bajo el **RUC anterior** (fecha original; ventana cerrada) |

Estados de las 233 a reversar en Key49: **223 `NOTIFIED` + 10 `AUTHORIZED`**
(todas vivas en el SRI).

### Efectos sobre la serie nueva (columna `colision` del CSV)

| `colision` | Casos | Acción |
|---|---|---|
| `VIVO_SIN_FACTURA` | **154** | La venta **nueva** (NEOGUAYAS) quedó **sin factura propia** → `vivo_accion = REEMITIR_NEOGUAYAS` |
| `VIEJO_LINKEADO_A_FACTURA_AJENA` | 21 | La venta vieja apunta a una factura del emisor nuevo (que es correcta) → desvincular |
| `LATENTE` | **76** | Número robado aún no alcanzado por el contador; se dispara solo → lo neutraliza el fix del 409 |
| `SIN_PAR_VIVO` | 1 | 10976 |
| `YA_NO_COLISIONA` | 2 | El par nuevo era $0.00 |

> Las **375** ventas del emisor anterior `CANCELLED` no se facturan (no aparecen
> en el CSV).

## 5. Caso 22294 — CORREGIDO (venta de NEOGUAYAS, 2026-09-18)

Estaba linkeada a la factura del cliente del emisor anterior. Se reemitió con
factura propia de NEOGUAYAS:

| Campo | Antes | Ahora |
|---|---|---|
| Secuencial | 003-501-000005748 (de 10976) | **003-501-000006802** |
| Fecha | 2026-09-11 | **2026-09-25** |
| `key49_invoice_id` | `3fa90a79…` | **`b3257d55-40da-4e78-af1b-c503f61a108b`** |
| Receptor | 1729802106 / $11.01 | **RUC 1690012606001 / $50.00** |

Contador `003-501`: 6802 → **6803**. Es el mismo procedimiento para las 154
ventas de NEOGUAYAS sin factura.

## 6. Cómo se reversan las 233

Key49 **soporta notas de crédito** (verificado por `OPTIONS`):

```
GET  /v1/credit-notes        → 200  {"data":[], ...}
OPTIONS /v1/credit-notes     → allow: HEAD, POST, GET, OPTIONS
```

La nota de crédito referencia la factura original y es la vía correcta ante el
SRI para dejarla sin efecto. **Falta el esquema del payload** (no está en
`docs/KEY49-INTEGRATION-GUIDE.md`); hay que obtenerlo de Key49 o validarlo en
sandbox. La app hoy **no** usa este endpoint.

## 7. Plan

1. **Fix de código (prioridad alta)** en `emitir_factura()` rama 409: comparar
   `recipient.id` y `total_amount`; si no coincide → no linkear, re-clavar con
   secuencial nuevo. Neutraliza las 76 latentes.
2. **Reversar las 233** con nota de crédito (requiere el payload de Key49).
3. **Reemitir las 154 ventas de NEOGUAYAS** sin factura propia.
4. **Resolver las 69 + 233 ventas del emisor anterior:** decisión fiscal +
   credenciales del tenant anterior. No reemitir con la clave de NEOGUAYAS.
5. `UNIQUE` en `key49_invoice_id` / `key49_access_key`.
6. **Causa origen:** nunca regenerar clave con el emisor/punto actuales si el
   despacho pertenece a otro emisor/serie; y soportar multi-emisor.

## 8. Referencias

- **Desglose + acciones (323 filas):** `docs/incidente_sri_2026-09-11_desglose.csv`
- SOP de reenvío: `docs/SOP_REENVIO_SRI_KEY49.md`
- Guía Key49 (`issue_date` = hoy, unicidad est+pto+secuencial): `docs/KEY49-INTEGRATION-GUIDE.md`
- Monitor SRI (Admin): `docs/admin/SRI_MONITOR.md`
