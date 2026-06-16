# ROADMAP de Desarrollo — Powerfin POS

## Principio

```
Una fase a la vez.
Entregable funcional al final de cada fase.
No se pasa a la siguiente sin validar la anterior.
Tests obligatorios antes de cada versión git.
```

---

## Resumen de fases

| Fase  | Nombre                      | Semanas | Entregable                                 |
| ----- | --------------------------- | ------- | ------------------------------------------ |
| **1** | Fundación FusionBridge      | 1       | TCP estable con Synergy + REST + SSE       |
| **2** | APIs en PowerFin            | 1       | Endpoints /api/pos/\* listos               |
| **3** | Powerfin POS base           | 2       | Login, turno, pantalla principal           |
| **4** | Flujo de venta completo     | 1       | Venta end-to-end con factura SRI           |
| **5** | Impresión                   | 1       | Tickets en impresora térmica de red ✅     |
| **6** | Funcionalidades adicionales | 1       | Caja, historial, usuarios en línea ✅     |
| **7** | Pruebas con hardware real   | 1       | Validación en GASOLINERA con dispensadores |
| **8** | POS Backend real            | 1       | FastAPI + PostgreSQL (reemplaza mock) ✅   |
| **9** | Integración y hardening     | 1       | POS ↔ Backend real ↔ FusionBridge          |
| **10**| Go-live                     | 1       | Deploy final, capacitación, producción     |

**Duración total estimada: 10 semanas**

---

## FASE 1 — Fundación FusionBridge (Semana 1)

### Objetivo

FusionBridge conectado al Wayne Synergy. Estado de surtidores visible vía REST y SSE.

### Tareas

**Día 1-2: Setup del proyecto**

```
[x] Crear proyecto Quarkus 3.x (Java 21)
[x] pom.xml con dependencias (Vert.x, REST, Scheduler, Health, escpos-coffee)
[x] application.properties con todas las variables de entorno
[x] Estructura de paquetes (fusion, dispenser, dispatch, print, sse, powerfin, health)
[x] Compilar sin errores: ./mvnw compile
```

**Día 3-4: FusionTcpClient**

```
[x] FusionMessage.java — parser con tests (35 tests, datos reales GASOLINERA)
[x] FusionMessageBuilder.java — constructor con tests (len correctamente calculado)
[x] FusionTcpClient.java
    [x] Conexión TCP a 192.168.1.20:3011 (Vert.x NetClient)
    [x] Buffer de lectura (mensajes terminados en ^)
    [x] ECHO keep-alive cada 120 segundos (@Scheduled)
    [x] Reconexión automática con backoff exponencial
    [x] sendSubscriptions() al conectar
[x] FusionEventHandler.java
    [x] handleStatusChange() → actualiza cache
    [x] handleNewTransaction() → empuja SSE
    [x] handleDeliveryProgress() → empuja SSE
[x] DispenserStatusCache.java — ConcurrentHashMap en memoria
```

**Día 5: SSE y REST básico**

```
[x] StationEventBus.java — broadcast a clientes SSE (BroadcastProcessor)
[x] DispenserResource.java — GET /api/dispensers
[x] BridgeHealthResource.java — GET /health
[x] SseEventResource.java — GET /api/events (SSE stream)
☐ Test manual: abrir browser, ver stream SSE actualizarse
```

**Día 6-7: Tests y validación**

```
[x] FusionMessageTest.java — parsear mensajes reales capturados de la GASOLINERA
[x] FusionMessageBuilderTest.java — verificar len correcto (19 tests)
[x] Compilar y ejecutar: ./mvnw test (35 tests, 100% pasan)
☐ Instalar como servicio systemd en servidor de pruebas
☐ Validar: echo ECHO | nc 192.168.1.20 3011 → responde
☐ Validar: GET /api/dispensers → retorna estado actual
☐ Validar: GET /api/events → stream SSE recibe cambios de estado
```

### Criterio de completitud

```
✅ ./mvnw test pasa sin errores (35 tests)
☐ FusionBridge conecta a 192.168.1.20:3011 (pendiente hardware)
☐ ECHO keep-alive responde correctamente (pendiente hardware)
☐ GET /api/dispensers retorna estado real del surtidor (pendiente hardware)
☐ Cambiar estado en consola Wayne → SSE lo refleja en < 1 segundo (pendiente hardware)
☐ Servicio systemd arranca y se recupera automáticamente (pendiente deploy)
✅ git tag v0.1.0 -m "Fase 1: FusionBridge TCP connection"
```

---

## FASE 2 — APIs en PowerFin (Semana 2)

### Objetivo

PowerFin tiene todos los endpoints REST que necesita el Powerfin POS.

### Tareas

**Día 1-2: Autenticación y configuración**

```
☐ POST /api/pos/auth/login (usuario + PIN con bcrypt)
☐ Tabla/campo para almacenar PIN hasheado en PowerFin
☐ Generación de JWT con datos del usuario
☐ GET /api/pos/config (dispensers, grades, price_lists)
```

**Día 3: Clientes y precios**

```
☐ GET /api/pos/customers?q={query} (placa, cédula, RUC, nombre)
☐ POST /api/pos/customers (registro nuevo)
☐ GET /api/pos/prices?customerId={id}&gradeId={grade}
```

**Día 4: Turnos**

```
☐ POST /api/pos/shifts/open
☐ GET  /api/pos/shifts/current
☐ POST /api/pos/shifts/{id}/close (con resumen)
```

**Día 5-6: Despachos**

```
☐ POST /api/pos/dispatches (crear orden, retornar OV-FECHA-SEQ)
☐ POST /api/pos/dispatches/{orderId}/complete (IDEMPOTENTE)
☐ POST /api/pos/dispatches/{orderId}/cancel
☐ GET  /api/pos/shifts/{shiftId}/dispatches
```

**Día 7: Movimientos y pruebas**

```
☐ POST /api/pos/cash-movements
☐ Probar todos los endpoints con curl o Postman
☐ Verificar idempotencia: llamar /complete dos veces → mismo resultado
```

### Criterio de completitud

```
✅ Login con PIN retorna JWT válido
✅ GET /config retorna dispensers y grades de la GASOLINERA
✅ Buscar "ABC-1234" retorna cliente con precio VIP
✅ Crear y completar una orden de despacho → PowerFin genera factura
✅ Abrir y cerrar turno correctamente
```

---

## FASE 3 — Powerfin POS base (Semanas 3-4)

### Objetivo

App funcional con login, apertura de turno y visualización de surtidores.

### Semana 3: Setup y autenticación

```
[x] Crear proyecto SvelteKit 2.x + TypeScript
[x] Instalar Tailwind CSS + adapter-static
[x] svelte.config.js con adapter-static
[x] src/lib/api/types.ts — todos los tipos TypeScript
[x] src/lib/api/powerfin.ts + powerfin.mock.ts — funciones login, config, customers, shifts, dispatches
[x] src/lib/api/bridge.ts + bridge.mock.ts — getDispensers, authorizeDispatch, getPrintPolicy, connectToEvents
[x] Stores: auth.ts, dispensers.ts, shift.ts, config.ts
[x] /login → LoginPage con PinKeyboard.svelte
[x] /shift/open → OpenShiftPage
[x] Layout auth guard (redirigir si no hay sesión o turno)
```

### Semana 4: Pantalla principal

```
[x] / → DispensersPage
    [x] Conectar SSE al montar el componente (bridge.mock.ts)
    [x] Grid de DispenserCard.svelte con colores por estado
    [x] Header con nombre del usuario y turno
    [x] OfflineBanner.svelte (si FusionBridge no responde)
[x] Tests con Vitest para APIs mock (15 tests)
[x] npm run check → 0 errores, 0 warnings
[x] npm run test → 15 tests pasan
[x] npm run build → build exitoso (adapter-static)
☐ Probar en celular real: npm run dev -- --host
```

### Criterio de completitud

```
✅ npm run test pasa
✅ Login con PIN en celular funciona
✅ Apertura de turno con selección de isla
✅ Pantalla de surtidores muestra estado en tiempo real
✅ Cambiar estado en Fusion → la app se actualiza sin recargar
✅ git tag v0.2.0 -m "Fase 3: Powerfin POS base"
```

---

## FASE 4 — Flujo de venta completo (Semana 5)

### Objetivo

Flujo end-to-end: desde buscar cliente hasta recibir factura SRI.

```
[x] /new-dispatch → NewDispatchPage
    [x] CustomerSearch.svelte con debounce
    [x] Mostrar precio según lista del cliente (VIP $1.100, STANDARD $1.500)
    [x] AmountInput.svelte con botones de monto rápido ($5/$10/$20/$50/$100)
    [x] Selector de forma de pago (EFECTIVO, TARJETA, QR, CREDITO)
    [x] AUTORIZAR → POST dispatches + POST authorize
[x] /fueling → FuelingPage
    [x] Estado en tiempo real via SSE (mock bridge)
    [x] Barra de progreso (volumen/monto)
    [x] Redirigir automáticamente al recibir IDLE (simula SALE_COMPLETED)
[x] /confirmation → ConfirmationPage
    [x] Resumen de la venta
    [x] Cálculo de vuelto si preset > monto real
    [x] Manejo de política de impresión (ALWAYS/ASK/NEVER) con PrintPrompt
    [x] Botón "Nueva venta"
[x] Vitest: 16 tests de flujo de venta (31 total)
☐ FusionBridge: DispatchService.completePayment() + notifyPowerFin() (pendiente Fase 7)
☐ FusionBridge: PendingSalesQueue (cola + retries + persistencia en disco) (pendiente Fase 7)
☐ Test con hardware real
```

### Criterio de completitud

```
✅ Flujo completo end-to-end funciona con Fusion simulado (mock)
✅ Cola de ventas pendientes funciona correctamente
✅ Preset por monto: vuelto calculado correctamente
✅ git tag v0.3.0 -m "Fase 4: Flujo de venta completo"
```

---

## FASE 5 — Impresión (Semana 6) ✅ COMPLETADA

### Objetivo

Tickets impresos en la impresora térmica de red de cada isla.

```
[x] FusionBridge — PrinterConfig.java
    [x] Leer IPs de impresoras desde variables de entorno
    [x] Leer política ALWAYS/ASK/NEVER
    [x] Configuración multi-isla con persistencia JSON en disco
    [x] API PUT /api/print/config para editar en runtime
    [x] Mapear isla → IP:puerto (cada surtidor tiene printer_island)
[x] FusionBridge — ReceiptBuilder.java
    [x] Construir datos de ticket desde request JSON
    [x] Manejo de campos opcionales (cliente, placa, factura)
[x] FusionBridge — TemplateRenderer.java
    [x] Motor de templates con placeholders {{variable}}
    [x] Bloques condicionales {#customer}...{/customer}, {#invoice}...{/invoice}
    [x] Directivas de formato: [BOLD], [CENTER], [CUT]
    [x] Separadores: --- (thin), === (bold)
    [x] Template por defecto profesional
    [x] API GET/PUT /api/print/template para editar templates
[x] FusionBridge — ThermalPrinter.java
    [x] Socket TCP directo a IP:9100
    [x] Timeout 5s y manejo de error si la impresora no responde
[x] FusionBridge — PrintResource.java
    [x] POST /api/print (con island-based routing)
    [x] POST /api/print/test (ticket de prueba)
    [x] GET /api/print/policy
    [x] GET/PUT /api/print/config
    [x] GET/PUT /api/print/template
    [x] Estado de impresoras en GET /health (IP + reachable)
[x] FusionBridge — PrintException.java
    [x] Excepción tipada para errores de impresión
[x] Powerfin POS — UI en SaleWizard (ConfirmationPage)
    [x] Consultar política vía bridge.getPrintPolicy()
    [x] ALWAYS → imprimir automáticamente
    [x] ASK → mostrar botones SÍ/NO
    [x] NEVER → no mostrar opción
    [x] Estados: imprimiendo, impreso ✅, error ⚠️
    [x] Botón reimprimir tras impresión exitosa
    [x] Botón reintentar en caso de error
    [x] Opción "Continuar sin ticket" (no bloquea la venta)
[x] Tests — 34 tests de impresión (12 PrinterConfig + 13 Template + 9 ReceiptBuilder)
[x] dispenser config incluye printer_island (PowerFin mock + Python server)
☐ Test físico: imprimir ticket de prueba en la impresora real (192.168.1.31)
```

### Criterio de completitud

```
✅ Templates editables vía API REST (GET/PUT /api/print/template)
✅ Config multi-isla persistente en JSON (GET/PUT /api/print/config)
✅ Política ALWAYS imprime sin preguntar
✅ Política ASK muestra botones SÍ/NO
✅ Política NEVER no muestra opción
✅ Error de impresora muestra mensaje claro, permite reintentar o continuar
✅ 34 tests de impresión pasando (69 total FusionBridge, 41 POS)
☐ Ticket imprime correctamente en impresora física 192.168.1.31 (pendiente hardware)
✅ git tag v0.5.0 -m "Fase 5: Thermal printing"
```

---

## FASE 6 — Funcionalidades adicionales (Semana 7) ✅ COMPLETADA

```
[x] /history → Historial del turno actual
    [x] Lista de despachos con estado, monto, cliente, placa, factura
    [x] Resumen parcial (ventas, monto)
    [x] Reimpresión de tickets desde el historial
    [x] Tab de movimientos de caja con saldo running
[x] /cash → Módulo de caja completo
    [x] Ingresos y egresos con valor + observación
    [x] Transferencias entre empleados y a Caja Fuerte
    [x] Saldo en tiempo real con running balance
[x] /users → Usuarios en línea
    [x] Dashboard con resumen general (usuarios activos, ventas, monto)
    [x] Detalle por usuario: ventas y total facturado del turno
[x] Refactor de turnos
    [x] Login sin redirect forzado a apertura de turno
    [x] Card "Abrir Turno" en dashboard con datos del usuario
    [x] Apertura con $0.00 fijo, solo confirmación
    [x] Bloqueo de operaciones sin turno abierto
☐ Cobertura de surtidor adicional ([+ Cubrir])
☐ Panel básico de supervisor (reportes del día)
```

---

## FASE 7 — Pruebas con hardware real (Semana 8)

### Objetivo

Validar todo con el Synergy conectado a los dispensadores físicos en la GASOLINERA.

```
☐ Ajustar ATO en consola Wayne de 0 → 180 segundos
☐ Prueba: despacho real de 1 litro de SUPER
☐ Prueba: cliente VIP → precio $1.100/litro aplicado en el dispensador
☐ Prueba: preset $50 → cliente despacha $43 → vuelto $7.00
☐ Prueba: cortar TCP → verificar reconexión automática en < 60s
☐ Prueba: apagar PowerFin 5 min → despachos → encender → sync automático
☐ Prueba: impresora desconectada → venta completa, error de impresión no bloquea
☐ Prueba: cerrar turno completo → cuadre en PowerFin
☐ Ajustar UI según feedback de despachadores reales
```

---

## FASE 8 — POS Backend real (Semana 9) ✅ COMPLETADA

### Objetivo

Reemplazar el simulador Python por un backend real con PostgreSQL.

### Tareas

```
[x] Diseño de schema: 26 tablas (POS_BACKEND.md)
[x] Proyecto FastAPI + SQLAlchemy 2.0 + asyncpg + Alembic
[x] Modelos SQLAlchemy para las 26 tablas
[x] Esquemas Pydantic (50+ request/response models)
[x] Servicios: auth (bcrypt+JWT), sequential (SRI atómico), credit (contratos)
[x] 38 endpoints REST (auth, config, vehicles, customers, persons, prices,
    shifts, dispatches CRUD, cash, transfers, credit contracts, products,
    dispatch types, identity lookup)
[x] Identity API: Sercobaco (CED) + SRI (RUC) con fallback local
[x] Contratos de crédito: INDEFINIDO/NO_INDEFINIDO, SERCOP, cupo disponible
[x] Decimal→float middleware para compatibilidad con POS
[x] Seed data: 4 usuarios, 6 productos, 8 métodos pago, 1 contrato
[x] 71 tests unitarios + integración — 100% pasando
[x] start.sh actualizado con comando "backend"
[x] Documentación: POS_BACKEND.md, IDENTITY_API.md, AGENTS.md actualizado
```

### Criterio de completitud

```
✅ 71/71 tests pasando
✅ Todos los endpoints del mock migrados a PostgreSQL real
✅ Identity API funcional con fallback
✅ Contratos de crédito con validación completa
✅ POS puede conectarse directamente (mismos formatos de respuesta)
✅ git tag v0.9.0 -m "Fase 8: POS Backend real"
```

---

## FASE 9 — Integración y hardening (Semanas 10-11) ✅ COMPLETADA

### Objetivo

Conectar el POS frontend al backend real y validar el sistema completo.

```
[x] Mapear nuevo dispensador (pumps 3, 4, 7, 8) en BD
[x] Prueba end-to-end: POS → pos_backend → FusionBridge → Synergy
[x] Integrar GET /api/pos/persons/lookup en el flujo de búsqueda del POS
[x] Probar multi-dispositivo con backend real
[x] Probar flujo de crédito desde el POS
[x] Ajustar ATO en consola Wayne de 0 → 180s
[x] Prueba de impresión térmica física (192.168.1.31:9100)
☐ Pruebas de carga y concurrencia → movido a Phase 10
```

### Entregado en 3 incrementos

| Tag | Contenido |
|-----|-----------|
| `v0.10.0` | Dispenser mapping, dispatch_details, multi-device sync, collect flow |
| `v0.11.0` | Price lists (VIP/EMPLOYEE), wizard reorder, emission points, schema simplification |
| `v0.12.0` | Cuadre de caja, transfers, persons/lookup, billing preferencial, auto-save, validación CED/RUC, registro mejorado, edición cliente |

### Criterio de completitud

```
✅ 184 tests pasando (72 FusionBridge + 71 Backend + 41 POS)
✅ POS conectado a backend real con PostgreSQL
✅ Identity API (Sercobaco/SRI) con auto-guardado local
✅ Facturación preferencial por vehículo
✅ Validación CED=10 / RUC=13 dígitos
✅ Flujo de registro de nueva persona completo
✅ Cuadre de caja con transfers y safe drops
✅ git tag v0.12.0 -m "Phase 9: Integration & hardening completed"
```

---

## FASE 10 — Edge cases + tech debt + go-live (Semanas 12-13)

### Objetivo

Resolver edge cases críticos antes del go-live y preparar despliegue.

### Tareas — Edge cases

```
[x] Cancelación a mitad del flujo (STOP durante FUELLING + rollback Gap D)
[x] Celular apagado/offline durante despacho (completeDispatch en FusionBridge)
[x] Ticket de impresión completo con datos desde BD
[x] Clave de acceso SRI (49 dígitos, módulo 11) + código numérico aleatorio
[x] Configuración de impresora desde BD (sin archivos JSON)
[x] Corrección subtotal/IVA (desglose correcto: total / 1.15)
[x] Espacio al final de impresión (6 líneas + punto antes del corte)
[x] Saldos negativos bloqueados en caja (validación egreso/transferencia/safe drop)
[x] Comprobantes de caja con impresión + reimpresión (ingreso/egreso/transferencia)
☐ Despacho con pago mixto (efectivo + tarjeta)
☐ Reconexión de FusionBridge durante despacho activo
☐ Múltiples despachos simultáneos (ambos lados del SURT-01)
```

### Tareas — Impresión y Cuadre de Caja

```
☐ Prueba de impresión térmica física (192.168.1.31:9100)
☐ Prueba de cuadre de caja end-to-end con hardware real
☐ Ajustar ATO en consola Wayne de 0 → 180s
```

### Tareas — Deuda técnica

```
☐ Migración Alembic para cambios de schema acumulados
☐ Revisar dispatch_details.quantity=0 inicial → NULL
☐ Verificar precios VIP/EMPLOYEE/FAMILY dinámicos end-to-end
```

### Tareas — Go-live

```
☐ Deploy definitivo en servidor Debian de producción
    ☐ Java 21 via SDKMAN
    ☐ Nginx configurado con SSL (certbot)
    ☐ systemd service fusion-bridge activado
    ☐ Verificar UPS conectado al servidor y al Synergy
    ☐ Verificar IP fija del servidor (192.168.1.10)
☐ Crear usuarios reales con PINs en PowerFin
☐ Configurar variable PRINTER_POLICY según política del cliente
☐ Capacitación despachadores (máx 30 min — la app es simple)
☐ Capacitación supervisor (apertura, cierre, reportes)
☐ Go-live con soporte presencial el primer día
☐ git tag v1.0.0 -m "Producción GASOLINERA"
```

---

## Orden de lectura de documentos para AGENTS Code

**Fase 1 (FusionBridge):**

```
1. FUSION_PROTOCOL.md   ← protocolo TCP validado con datos reales
2. FUSION_BRIDGE.md     ← arquitectura y código base
3. INFRAESTRUCTURA.md   ← systemd, Nginx, deploy en Debian
```

**Fase 2 (APIs PowerFin):**

```
1. API_CONTRACT.md      ← contrato completo de endpoints
2. FLUJOS_OPERATIVOS.md ← flujos de negocio
```

**Fases 3-6 (Powerfin POS):**

```
1. POWERFIN_POS.md      ← arquitectura SvelteKit
2. API_CONTRACT.md      ← endpoints que consume
3. FLUJOS_OPERATIVOS.md ← pantallas y flujos
```

**Fase 8 (POS Backend):**

```
1. POS_BACKEND.md       ← schema, APIs, reglas de negocio
2. IDENTITY_API.md      ← integración Sercobaco/SRI
3. API_CONTRACT.md      ← contratos de endpoints
```

---

## Versionado por fase

| Al completar | Tag git  | Versión                            |
| ------------ | -------- | ---------------------------------- |
| Fase 1       | `v0.1.0` | FusionBridge TCP                   |
| Fase 2       | interno  | APIs PowerFin (no versiona el POS) |
| Fase 3       | `v0.2.0` | Powerfin POS base                  |
| Fase 4       | `v0.3.0` | Flujo de venta                     |
| Fase 5       | `v0.5.0` | Impresión ✅                       |
| Fase 6       | `v0.6.0` | Caja + historial + usuarios ✅     |
| Fase 7       | `v0.7.0` | Pruebas hardware real              |
| Fase 8       | `v0.9.0` | POS Backend real (FastAPI+PG) ✅   |
| Fase 9a      | `v0.10.0`| Dispenser mapping, sync, collect   |
| Fase 9b      | `v0.11.0`| Price lists, wizard, schema        |
| Fase 9c      | `v0.12.0`| Cuadre, lookup, billing, registro  |
| Fase 10a     | `v0.13.0`| Edge cases: STOP, phone-off, Gap D |
| Fase 10b     | `v0.14.0`| Impresión, clave SRI, DB config    |
| Fase 10c     | `v0.15.0`| Correcciones: IVA, aleatorio, corte, saldo, comprobantes ✅ |
| Fase 10d     | `v0.16.0`| Key49: facturación electrónica SRI |
| Fase 11a     | `v0.19.0`| UX, refactors, ID-based, SRI code, name search, predefined plates |
| Fase 11b     | `v0.19.1`| Bugfix: recovery AUTHORIZED dispatch cuando PAY_IN no eco-devuelto (phone-off) |
| Fase 11      | `v1.0.0` | Producción GASOLINERA              |
