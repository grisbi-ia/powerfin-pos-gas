# SOP — Destrabar un surtidor en `PAUSED`

> **Propósito**: Liberar un surtidor Wayne Synergy que quedó retenido en estado `PAUSED`
> y cerrar correctamente la venta que quedó abierta, **sin editar la base de datos a mano**.

```
Última actualización: 2026-10-16 (v0.39.4)
Relacionado: docs/FUSION_PROTOCOL.md · docs/TOPOLOGIA_DISPENSADORES.md · docs/DEPLOY_QUICK.md
```

---

## 1. Síntomas

- El POS muestra la pistola en **`PAUSED`** (morado) y no deja volver a usarla.
- La venta queda **abierta**: el despacho está `AUTHORIZED` con `total = 0.00`.
- En la pantalla del surtidor se ve el **monto real** de la carga (ej. `37.36`).
- **No llega** el `EVT_PUMP_NEW_TRANSACTION` → el POS nunca se entera de cuánto se despachó.
- Puede durar horas: **no se libera solo**.

---

## 2. Causa raíz: `PresetOverrun`

Si el cliente llega al **preset de VOLUMEN** y el surtidor se sobrepasa, el firmware cierra
la carga con motivo `[15][PresetOverrun]` y **deja el surtidor en `PAUSED` en vez de pasar a
`EOT`**. Consecuencia:

- El surtidor **no emite `EVT_PUMP_NEW_TRANSACTION`** y no libera la pistola.
- La venta queda abierta de los dos lados (POS y firmware).

> Caso real (bomba 5, NEOGAS, 2026-10-16): preset `12.000` gal → entregó **`12.062`** gal por
> `$37.360`, motivo `PresetOverrun`. Quedó **~5 h en `PAUSED`**.

El flag de pausa es un **latch independiente** del de stop. Por eso `STOP` y `CLEAR_STOP`
no lo limpian.

---

## 3. Diagnóstico (30 segundos)

```bash
# 1) Ver qué bombas están retenidas (fusionPumpId 1-8)
curl -s http://<servidor>:8090/api/dispensers | python3 -m json.tool | grep -B2 -A2 PAUSED

# 2) Confirmar que no llegó la transacción: despachos abiertos en la BD
#    (solo SELECT)
SELECT dispatch_id, order_id, status, dispenser_id, hose_id, total, created_at
FROM dispatches
WHERE status IN ('AUTHORIZED','COMPLETED') AND total = 0
ORDER BY created_at DESC LIMIT 10;

# 3) Ver la traza del bridge
sudo journalctl -u fusion-bridge --since "2 hours ago" | grep -iE "Dispenser <N>|PAUSED"
```

---

## 4. Solución: `REQ_PUMP_REAUTH`

**Un solo comando.** Es el único que ejecuta `eaClearPause` en el firmware — el
`Clear_Pause` del diagrama de estados.

```bash
curl -s -X POST http://<servidor>:8090/api/dispatch/reauth \
  -H 'Content-Type: application/json' \
  -d '{"dispenser_id":<PUMP>}'
# → {"status":"REAUTH_SENT"}
```

> ⚠️ **`dispenser_id` es el número de *pump* del Fusion (1–8), NO el del armario (1–4).**
> Un armario tiene dos pumps. Ver `docs/TOPOLOGIA_DISPENSADORES.md`.
> Armario 1 → pumps 1,2 · Armario 2 → pumps 3,4 · **Armario 3 → pumps 5,6** · Armario 4 → pumps 7,8.

Ejemplo (bomba 5): `-d '{"dispenser_id":5}'`

**Qué hace el firmware** (orden real, en menos de 5 s):

```
REQ_PUMP_REAUTH_ID_005
  → eaClearPause                     “Pump Pause Event processed OK”
  → PAUSED → EOT
  → iaReadPumpLastSale               lee volumen y monto REALES
  → sendLastSaleInfo                 emite EVT_PUMP_NEW_TRANSACTION
  → EOT → IDLE
```

`REAUTH_SENT` en la respuesta **no** significa “liberado”: el bridge solo confirma que
escribió al socket. El resultado real llega por SSE. Verificá con el paso 5.

> **Ojo**: `REAUTH` reautoriza la transacción retenida. Si la pistola está fuera del soporte,
> el surtidor podría reanudar el despacho. Enviálo con un operador en la bomba.

---

## 5. Verificación

```bash
curl -s http://<servidor>:8090/api/dispensers | python3 -m json.tool | grep -A3 '"dispenserId": <PUMP>'
# esperado: "status": "IDLE"

sudo journalctl -u fusion-bridge -f | grep -iE "Dispenser <N>"
# esperado: PAUSED → ... → IDLE  y el log de NEW_TRANSACTION
```

En el POS aparece el despacho como **`COMPLETED`** con el volumen y el monto reales →
ya se puede **cobrar** e **imprimir/facturar** normalmente.

---

## 6. Qué NO sirve (verificado contra hardware real)

| Intento | Respuesta del Wayne | Efecto |
| --- | --- | --- |
| `REQ_PUMP_CLOSE` (botón **“Cerrar”** de la consola Synergy) | `SSF_TRANS_ERR_CLOSE_IN_STATE [PAUSED]` | ❌ rechazado |
| `REQ_PUMP_STOP` con `PA=1` (botón Stop del POS) | `eaStop - Stop Pump OK **With Pause**` → `isStopped=1` | ❌ deja el latch de PAUSE |
| `REQ_PUMP_CLEAR_STOP` | `eaClearStop - CLEAR STOP PUMP OK` → `isStopped=0` | ❌ limpia STOP, no PAUSE |
| Reiniciar FusionBridge (nuestro bridge) | — | ❌ sin efecto |
| Colgar/levantar la pistola | — | ❌ sin efecto |
| Reiniciar la aplicación Fusion | — | ❌ sin efecto |

---

## 7. ⛔ Nunca cerrar la venta editando la BD

Está **prohibido** marcarla `COLLECTED` por SQL (o insertar el pago a mano) para poder
facturar. Eso fue exactamente lo que pasó el **2026-10-16** con el despacho **29504**:
intervención manual de dos transacciones, con el pago **backdateado** y `completed_at`
copiado de `created_at`. Consecuencias:

- **Volumen en 0** en el detalle → reportes de galones y precio/galón incorrectos.
- Nada queda en el log de la app (`log_statement = none`, sin auditoría) → el origen es
  indetectable después.
- Se pierde el flujo normal de facturación.

**El camino correcto es el paso 4**: `REAUTH` → el Wayne emite la transacción → se cobra y
se factura normalmente. **No hace falta tocar la BD.**

### Si ya se cerró a mano (recuperar datos)

El Wayne sí tiene la venta real en su propia base. El dato autoritativo del volumen sale de
ahí (`Saved Volume`), o del log del bridge en el evento `NEW_TRANSACTION`:

```sql
-- Corregir el detalle con el volumen y totales reales del surtidor
UPDATE dispatch_details
   SET quantity = <volumen_real>, subtotal = <total/1.15>, tax_amount = <total - total/1.15>,
       total = <total_real>
 WHERE detail_id = <id> AND dispatch_id = <dispatch_id> AND quantity = 0;
```

> Nota: tras un cierre manual, el `NEW_TRANSACTION` tardío **se ignora a propósito** (el
> backend responde `already completed with totals`) porque el despacho ya está `COLLECTED`.
> Por eso el volumen hay que corregirlo a mano en ese caso, y solo en ese caso.

---

## 8. Prevención (pendiente)

- **Botón “Destrabar” en el POS/Admin**: verificar `PAUSED` y enviar `REAUTH` desde la UI,
  con confirmación. Hoy solo existe el endpoint crudo.
- **Detección automática**: alertar cuando un surtidor lleva N minutos en `PAUSED` con un
  despacho `AUTHORIZED` asociado. *(Cualquier automatismo necesita activación explícita y
  aprobación — AGENTS.md prohíbe los fallbacks silenciosos.)*
- **Fix de raíz en el bridge**: el falso éxito de `POST /api/dispatch/stop` — hoy devuelve
  `{"status":"STOPPED"}` con solo escribir al socket, e **ignora** los `RES_GENERIC_ERROR`
  del Wayne (se loguean como `Unhandled event (new Wayne event type?)`).
