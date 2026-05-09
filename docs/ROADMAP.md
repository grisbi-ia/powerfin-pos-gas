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
| **5** | Impresión                   | 1       | Tickets en impresora térmica de red        |
| **6** | Funcionalidades adicionales | 1       | Historial, caja, cobertura, cierre         |
| **7** | Pruebas con hardware real   | 1       | Validación en GASOLINERA con dispensadores |
| **8** | Go-live                     | 1       | Deploy final, capacitación, producción     |

**Duración total estimada: 9 semanas**

---

## FASE 1 — Fundación FusionBridge (Semana 1)

### Objetivo

FusionBridge conectado al Wayne Synergy. Estado de surtidores visible vía REST y SSE.

### Tareas

**Día 1-2: Setup del proyecto**

```
☐ Crear proyecto Quarkus 3.x (Java 21)
☐ pom.xml con dependencias (Vert.x, REST, Scheduler, Health, escpos-coffee)
☐ application.properties con todas las variables de entorno
☐ Estructura de paquetes (fusion, dispenser, dispatch, print, sse, powerfin, health)
☐ Compilar sin errores: ./mvnw compile
```

**Día 3-4: FusionTcpClient**

```
☐ FusionMessage.java — parser con tests
☐ FusionMessageBuilder.java — constructor con tests (calcular len correctamente)
☐ FusionTcpClient.java
    ☐ Conexión TCP a 192.168.1.20:3011
    ☐ Buffer de lectura (mensajes terminados en ^)
    ☐ ECHO keep-alive cada 120 segundos
    ☐ Reconexión automática con backoff exponencial
    ☐ sendSubscriptions() al conectar
☐ FusionEventHandler.java
    ☐ handleStatusChange() → actualiza cache
    ☐ handleNewTransaction() → dispara completePayment()
    ☐ handleDeliveryProgress() → empuja SSE
☐ DispenserStatusCache.java — Map en memoria
```

**Día 5: SSE y REST básico**

```
☐ StationEventBus.java — broadcast a clientes SSE conectados
☐ DispenserResource.java — GET /api/dispensers
☐ BridgeHealthResource.java — GET /health
☐ GET /api/events — SSE stream
☐ Test manual: abrir browser, ver stream SSE actualizarse
```

**Día 6-7: Tests y validación**

```
☐ FusionMessageTest.java — parsear mensajes reales capturados de la GASOLINERA
☐ FusionMessageBuilderTest.java — verificar len correcto
☐ Compilar y ejecutar: ./mvnw test (todos deben pasar)
☐ Instalar como servicio systemd en servidor de pruebas
☐ Validar: echo ECHO | nc 192.168.1.20 3011 → responde
☐ Validar: GET /api/dispensers → retorna estado actual
☐ Validar: GET /api/events → stream SSE recibe cambios de estado
```

### Criterio de completitud

```
✅ ./mvnw test pasa sin errores
✅ FusionBridge conecta a 192.168.1.20:3011
✅ ECHO keep-alive responde correctamente
✅ GET /api/dispensers retorna estado real del surtidor
✅ Cambiar estado en consola Wayne → SSE lo refleja en < 1 segundo
✅ Servicio systemd arranca y se recupera automáticamente
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
☐ Crear proyecto SvelteKit 2.x + TypeScript
☐ Instalar Tailwind CSS + Lucide Svelte + @vite-pwa/sveltekit
☐ svelte.config.js con adapter-static
☐ src/lib/api/types.ts — todos los tipos TypeScript
☐ src/lib/api/powerfin.ts — funciones login, config, customers, shifts, dispatches
☐ src/lib/api/bridge.ts — getDispensers, authorizeDispatch, getPrintPolicy, connectToEvents
☐ Stores: auth.ts, dispensers.ts, shift.ts, config.ts
☐ /login → LoginPage con PinKeyboard.svelte
☐ /shift/open → OpenShiftPage
☐ Layout auth guard (redirigir si no hay sesión o turno)
```

### Semana 4: Pantalla principal

```
☐ / → DispensersPage
    ☐ Conectar SSE al montar el componente
    ☐ Grid de DispenserCard.svelte con colores por estado
    ☐ Header con nombre del usuario y turno
    ☐ OfflineBanner.svelte (si FusionBridge no responde)
☐ Tests con Vitest para stores y funciones de API (mocks)
☐ npm run check → sin errores de tipos
☐ npm run test → todos pasan
☐ npm run build → build exitoso
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
☐ /new-dispatch → NewDispatchPage
    ☐ CustomerSearch.svelte con debounce
    ☐ Mostrar precio según lista del cliente
    ☐ AmountInput.svelte con botones de monto rápido ($5/$10/$20/$50/$100)
    ☐ Selector de forma de pago
    ☐ AUTORIZAR → POST dispatches + POST authorize
☐ /fueling → FuelingPage
    ☐ Estado en tiempo real via SSE
    ☐ Barra de progreso (volumen/monto)
    ☐ Redirigir automáticamente al recibir SALE_COMPLETED
☐ /confirmation → ConfirmationPage
    ☐ Resumen de la venta con factura
    ☐ Cálculo de vuelto si preset > monto real
    ☐ Manejo de política de impresión (ALWAYS/ASK/NEVER)
    ☐ Botón "Nueva venta"
☐ FusionBridge: DispatchService.completePayment() + notifyPowerFin()
☐ FusionBridge: PendingSalesQueue (cola + retries + persistencia en disco)
☐ Test: apagar PowerFin → hacer venta → encender → verificar sincronización
```

### Criterio de completitud

```
✅ Flujo completo end-to-end funciona con Fusion simulado (mock)
✅ Cola de ventas pendientes funciona correctamente
✅ Preset por monto: vuelto calculado correctamente
✅ git tag v0.3.0 -m "Fase 4: Flujo de venta completo"
```

---

## FASE 5 — Impresión (Semana 6)

### Objetivo

Tickets impresos en la impresora térmica de red de cada isla.

```
☐ FusionBridge — PrinterConfig.java
    ☐ Leer IPs de impresoras desde variables de entorno
    ☐ Leer política ALWAYS/ASK/NEVER
    ☐ Mapear dispenser_id → impresora de la isla
☐ FusionBridge — ReceiptBuilder.java
    ☐ Generar bytes ESC/POS con escpos-coffee
    ☐ Encabezado, datos del despacho, factura, pie
    ☐ Manejo de campos opcionales (cliente, placa, factura)
☐ FusionBridge — ThermalPrinter.java
    ☐ Socket TCP directo a IP:9100
    ☐ Timeout y manejo de error si la impresora no responde
☐ FusionBridge — PrintResource.java
    ☐ POST /api/print
    ☐ GET /api/print/policy
    ☐ Incluir estado de impresoras en GET /health
☐ Powerfin POS — PrintPrompt.svelte + lógica en ConfirmationPage
    ☐ Consultar política al arrancar (loadConfig)
    ☐ ALWAYS → imprimir automáticamente
    ☐ ASK → mostrar botones SÍ/NO
    ☐ NEVER → no mostrar opción
☐ Test físico: imprimir ticket de prueba en la impresora real
☐ ReceiptBuilderTest.java — verificar bytes generados
```

### Criterio de completitud

```
✅ Ticket imprime correctamente en impresora 192.168.1.31
✅ Política ALWAYS imprime sin preguntar
✅ Política ASK muestra botones
✅ Política NEVER no muestra opción
✅ Error de impresora muestra mensaje claro (no bloquea la venta)
✅ git tag v0.4.0 -m "Fase 5: Thermal printing"
```

---

## FASE 6 — Funcionalidades adicionales (Semana 7)

```
☐ /history → Historial del turno actual
    ☐ Lista de despachos con estado
    ☐ Resumen parcial (ventas, volumen, monto)
☐ /shift/close → Cierre de turno
    ☐ Resumen completo
    ☐ Ingreso de efectivo en caja
    ☐ Mostrar diferencia
    ☐ Imprimir reporte de turno
☐ Movimientos de caja (ingreso/egreso)
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

## FASE 8 — Go-live (Semana 9)

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
1. POWERFIN_POS.md          ← arquitectura SvelteKit
2. API_CONTRACT.md      ← endpoints que consume
3. FLUJOS_OPERATIVOS.md ← pantallas y flujos
```

---

## Versionado por fase

| Al completar | Tag git  | Versión                            |
| ------------ | -------- | ---------------------------------- |
| Fase 1       | `v0.1.0` | FusionBridge TCP                   |
| Fase 2       | interno  | APIs PowerFin (no versiona el POS) |
| Fase 3       | `v0.2.0` | Powerfin POS base                  |
| Fase 4       | `v0.3.0` | Flujo de venta                     |
| Fase 5       | `v0.4.0` | Impresión                          |
| Fase 6       | `v0.5.0` | Funcionalidades completas          |
| Fase 8       | `v1.0.0` | Producción GASOLINERA              |
