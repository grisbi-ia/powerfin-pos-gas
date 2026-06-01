# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-01)

### ✅ Fases completadas

| Fase | Tag | Descripción |
|------|-----|-------------|
| 1 | `v0.1.0` | FusionBridge TCP connection |
| 2 | — | APIs PowerFin documentadas (21 endpoints) |
| 3 | `v0.2.0` | Powerfin POS base — login, surtidores |
| 4 | `v0.3.0` | Flujo de venta completo |
| 5 | `v0.5.0` | Impresión térmica — ESC/POS, config multi-isla, templates editables |
| 5.1 | `v0.6.0` | Módulo de caja + refactor turnos + historial + usuarios en línea |
| 6 | `v0.7.0` | Validación hardware real — Wayne Synergy |
| 6.1 | `v0.7.1` | Bugfix: match IDs dispensador/manguera, flujo de cobro |
| 6.2 | `v0.8.0` | Sincronización multi-dispositivo + cancelación manual |
| 6.3 | `v0.8.1` | Fix customer_name cross-device |
| 6.4 | `v0.8.2` | Cambio de facturación post-despacho |
| 6.5 | `v0.8.3` | Eliminación Consumidor Final + offline detection + fixes varios |

### 📊 Tests

```bash
# FusionBridge — 72 tests
cd fusion-bridge && ./mvnw test   # BUILD SUCCESS

# POS — 41 tests (Vitest)
cd pos && npm run test            # 41 passed

# Total: 113 tests pasando
```

---

## Logros de la sesión 2026-06-01

### 1. Sincronización multi-dispositivo (v0.8.0) ✅

**4 capas de protección:** SSE `NEW_TRANSACTION` (<1s), reconciliación PowerFin (3s), verificación bajo demanda al hacer clic (~300ms), botón refresco manual.

### 2. Botón cancelación manual (v0.8.0) ✅

Cancelar autorización sin esperar ATO 180s. Solo en AUTHORIZED/CALLING/STARTING, solo para el usuario que autorizó, con diálogo de confirmación.

### 3. Bugfix: CLEAR_PRESET al pump correcto (v0.8.0) ✅

`cancelDispenser` ahora envía `fusionPumpId` del hose (config) en vez del `dispenserId` del armario.

### 4. Bugfix: `authorized_by` por usuario real (v0.8.0) ✅

`SaleWizard` envía `$currentUser.name` en vez de `$shift.user_name`. `handleOpenShift` envía `user_name`. Servidor Python usa `body.get("authorized_by", ...)`.

### 5. Bugfix: PowerFin COMPLETED vía SSE (v0.8.0) ✅

`NEW_TRANSACTION` ahora llama `powerfin.completeDispatch()` (fire-and-forget) para que otros dispositivos vean COMPLETED al reconciliar.

### 6. Bugfix: verificación consulta todos los pumps (v0.8.0) ✅

`handleSideClick` usa `pollDispensers()` (todos los pumps) en vez de `getDispenser(id)` (un solo pump).

### 7. Fix customer_name cross-device (v0.8.1) ✅

`SaleWizard` envía `customer_name` en `createDispatch()`. PowerFin lo almacena. Reconciliación lo muestra en todos los dispositivos.

### 8. Cambio de facturación post-despacho (v0.8.2) ✅

En modo cobro, cambiar destinatario de factura por cédula/RUC. La placa no cambia. Nuevo endpoint `POST /api/pos/dispatches/{id}/billing`.

### 9. Eliminación Consumidor Final (v0.8.3) ✅

Por regulación SRI, todas las ventas requieren cliente identificado. Eliminados: `handleSkipPlate()`, botón "Sin identificar", `handleChangeToConsumer()`, botón "Facturar a Consumidor Final". Fallbacks cambiados a `'Sin nombre'`.

### 10. Sincronización formas de pago (v0.8.3) ✅

Servidor Python ahora tiene 7 métodos: EFECTIVO, TARJETA, QR, CREDITO, DEUNA, JEPFAST, SIPY.

### 11. Detección de Synergy offline (v0.8.3) ✅

Al perder conexión TCP con Synergy, todos los dispensadores se marcan `connected=false` (opacidad 50% + "offline"). Fix en `convertToDispenserState` + `setFusionConnected`.

### 12. API_CONTRACT.md actualizado ✅

Documentadas todas las APIs nuevas: billing, collect, payment-lock/clear/unlock, SSE events, arquitectura multi-dispositivo, flujos de cancelación y cambio de facturación.

---

## Configuración actual del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores | 1 físico (DIESEL, 2 lados) → 2 pumps lógicos en Synergy |
| Combustible | DIESEL (Grade 3, P3) |
| Precio | $3.103/galón |
| Pump 1 → Side A | Fusion hose 1 |
| Pump 2 → Side B | Fusion hose 1 |
| ATO | 180s |
| Moneda | DÓLARES ($) |
| Firmware | Rel-5.19.1 |
| Formas de pago | EFECTIVO, TARJETA, QR, CREDITO, DEUNA, JEPFAST, SIPY |
| Cliente requerido | Sí (cédula o RUC obligatorio — sin Consumidor Final) |

---

## Cómo arrancar todo

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas

# Limpiar estado viejo (primera vez o después de cambios en powerfin_server.py)
./start.sh stop
rm -f tools/powerfin_state.json

# Arrancar
./start.sh powerfin  # PowerFin mock :8080
./start.sh bridge    # FusionBridge :8090 (tarda ~15s)
./start.sh pos       # POS :5173

# Control:
./start.sh stop      # Detener todo
./start.sh status    # Ver estado

# Diagnosticar Synergy:
python3 tools/info_fusion.py
```

Abrir: **`http://192.168.1.113:5173`** | Login: `carlos` / `1234` o `maria` / `1234`

---

## Pendiente para la próxima sesión

### 🔥 Prioridad 0 — Integración con PowerFin ERP real (MAÑANA)

El PowerFin ERP real (OpenXava/Java 8/PostgreSQL/:8080) está disponible.
El POS ya está listo — solo hay que agregar los endpoints `/api/pos/*` al ERP.

```
☐ Agregar endpoints al PowerFin ERP (21 endpoints en API_CONTRACT.md)
☐ POST /api/pos/auth/login
☐ GET  /api/pos/config
☐ GET  /api/pos/vehicles?plate=
☐ GET  /api/pos/customers?q=
☐ GET  /api/pos/customers/by-id?id_type=&id_number=
☐ POST /api/pos/customers
☐ GET  /api/pos/prices?customerId=&gradeId=
☐ POST /api/pos/shifts/open
☐ GET  /api/pos/shifts/current
☐ POST /api/pos/shifts/{id}/close
☐ POST /api/pos/dispatches
☐ POST /api/pos/dispatches/{id}/complete
☐ POST /api/pos/dispatches/{id}/collect
☐ POST /api/pos/dispatches/{id}/cancel
☐ POST /api/pos/dispatches/{id}/billing
☐ GET  /api/pos/shifts/{id}/dispatches
☐ POST /api/pos/cash-movements
☐ GET  /api/pos/shifts/{id}/cash-movements
☐ GET  /api/pos/shifts/{id}/cash-summary
☐ GET  /api/pos/users/online
☐ POST /api/pos/transfers
☐ Conectar POS al ERP → cambiar URL en vite.config.ts
☐ Quitar powerfin_server.py (ya no es necesario)
☐ Probar flujo completo: login → turno → venta → cobro → cierre turno
☐ Probar multi-dispositivo (2 tablets)
```

### 🔴 Prioridad 1 — Despachos a crédito, calibraciones y pruebas

Actualmente solo existe venta de combustible normal. Se necesita:

```
☐ Despachos a crédito (empresas con cupo)
   - El sistema debe verificar saldo disponible antes de autorizar
   - No se cobra en el momento — se registra como crédito
   - Posible integración con módulo de crédito de PowerFin ERP

☐ Salidas por calibración
   - Despachos sin cliente ni factura (consumo interno)
   - Deben quedar registrados como "CALIBRACION" para trazabilidad
   - No afectan caja ni facturación

☐ Salidas por pruebas
   - Similar a calibración pero con categoría "PRUEBA"
   - Puede requerir selección de motivo
```

### 🟠 Prioridad 2 — Venta de productos adicionales

```
☐ Registrar venta de: ambientales, aditivos, aceites, etc.
☐ Factura independiente (no mezclada con combustible)
☐ Flujo rápido: seleccionar producto → cantidad → cobrar
☐ Catálogo de productos configurable desde PowerFin
☐ Afecta caja e inventario
```

### 🟡 Prioridad 3 — Lecturas cronometradas de dispensadores

```
☐ Registrar periódicamente las métricas del dispensador
   - Totalizadores (volumen acumulado, monto acumulado)
   - Lecturas por turno, diarias, semanales
☐ Almacenar en PowerFin para reportes del ente regulador (ARCH)
☐ Posible automatización: cada N minutos consultar métricas vía Fusion
☐ Interfaz para visualizar historial de lecturas
```

### 🟢 Prioridad 4 — Bug: validación de input numérico (montos/galones)

```
☐ Revisar el parseo de valores decimales en el input de monto/galones
☐ El error puede estar en:
   - Separador decimal (coma vs punto) según locale
   - Cantidad de decimales permitidos
   - Valores negativos o cero
☐ Agregar validación antes de enviar a autorizar
☐ Mostrar mensaje claro si el valor no es válido
```

### 🔵 Prioridad 5 — Pendientes anteriores

```
☐ Prueba de impresión térmica en 192.168.1.31:9100
☐ Prueba de topologías de dispensadores (2+ físicos, multi-manguera)
☐ Integración con PowerFin ERP real
```

---

## NOTAS

- `plate = 'ABC1234'` está hardcodeado en `SaleWizard.svelte:28` para pruebas. Remover ANTES de producción.
- El dispensador físico requiere **palanca manual** además de levantar la pistola (equipo antiguo)
- `SUBSCRIBE|ALL` es necesario en firmware Rel-5.19.1 (suscripciones individuales no funcionan)
- El cambio de precio por protocolo requiere aprobación manual en consola (módulo "Price Change Add In")
- Siempre `rm -rf .svelte-kit` al reiniciar el POS para evitar caché de Vite
- **NO usar `LID` ni `LM` en PRESET** — firmware Rel-5.19.1 crea locks permanentes
- `localStorage` es caché local, NO source of truth. PowerFin vía reconciliación cada 3s es la autoridad.
- Al reiniciar `powerfin_server.py`, borrar `tools/powerfin_state.json` para evitar datos inconsistentes.
- **No existe Consumidor Final** — toda venta requiere cliente con cédula o RUC.
