# Flujos de Venta de Combustible — Powerfin POS

> Documento de definición operativa. Todos los escenarios posibles en una venta.
> Se revisa, se ajusta, y luego se plasma en código.

---

## Reglas generales (aplican a todos los escenarios)

### Regla 1 — El que cobra es el dueño de la venta

El `shift_id` de una orden NO se define al autorizar, sino **al cobrar**.

- Juan autoriza la venta → orden creada con `shift_id` temporal de Juan.
- Si Juan cobra → la orden queda en el turno de Juan.
- Si María cobra → PowerFin actualiza el `shift_id` al turno de María.
- El dinero va a la caja de quien cobró.
- Al cerrar turno, cada despachador cuadra SOLO las ventas que él/ella cobró.

PowerFin expone un endpoint de cobro (no de "complete"):

```
POST /api/pos/dispatches/{orderId}/collect
{
    "collected_by_shift_id": 48,
    "payment_method": "EFECTIVO",
    "collected_amount": 42.50,
    "change_amount": 7.50
}
```

### Regla 2 — Dashboard muestra "Pendiente de Cobro" a todos

Cuando una venta se completa en el Fusion (pistola colgada, factura emitida), el estado
en el dashboard cambia a **"Pendiente de Cobro"**. Este estado es visible para TODOS los
despachadores. Cualquiera puede tocar y cobrar. La pistola ya está libre para la siguiente
venta (el Fusion la liberó).

### Regla 3 — El despachador elige tipo de preset: Monto o Galones

Antes de ingresar el valor, el despachador (o cliente) elige:
- **Por Monto:** "Póngame $20 de Super" → `preset_type='MONEY'`
- **Por Galones:** "Póngame 5 galones de Extra" → `preset_type='VOLUME'`

### Regla 4 — No hace falta ver progreso en tiempo real

El despachador autoriza y puede volver al dashboard. El dashboard muestra el estado
actual del lado (Autorizado, Despachando). Si quiere ver detalle, toca el lado. Pero
no es necesario quedarse mirando la barra de progreso.

### Regla 5 — Layout físico viene de PowerFin

Cada gasolinera tiene su propia configuración de surtidores, lados y mangueras.
El POS recibe todo de `GET /api/pos/config`. Nada está hardcodeado.

---

## Escenario 1 — Venta normal, datos completos

```
1. Despachador ve pantalla principal (dashboard) con todos los surtidores.
2. Toca Lado A del Surtidor 1 (estado: Disponible).
3. Wizard muestra selector de pistola (grado de combustible):
   - Si el lado tiene 1 sola pistola → avanza automáticamente.
   - Si tiene 2+ pistolas → el despachador selecciona una (Super, Extra, Diesel).
4. Wizard muestra input de placa con botón Buscar.
   También muestra opción secundaria: "Sin identificar (Consumidor Final)".
5. Despachador ingresa "ABC1234" y presiona Buscar.
6. PowerFin responde: vehicle_found=true, incomplete_fields=[], dueño completo.
7. Wizard muestra BillingConfirmation:
   - "Juan Carlos Pérez — Cédula: 0912345678 — VIP"
   - Precio se actualiza a $1.100/L.
   - Botones: "✓ Correcto" y "Cambiar".
8. Despachador presiona "Correcto".
9. Wizard muestra selector de tipo de preset:
   - "💵 Por Monto" ($)
   - "⛽ Por Galones" (galones)
10. Cliente elige "Por Monto". Wizard muestra campo de monto:
    - Input numérico grande + botones rápidos $5, $10, $20, $50, $100.
    - Opción "Llenar tanque".
    - Litros estimados en tiempo real: monto ÷ $1.100.
11. Despachador ingresa $50.00 y presiona "Autorizar Despacho".
12. POS crea orden en PowerFin → recibe OV-001.
    orden: shift_id temporal = turno de quien autoriza.
13. POS envía preset a FusionBridge:
    REQ_PUMP_PRESET_ID_001, HO=1@1.100, TY=MONEY, VA=50.00,
    PAY_IN=OV=OV-001~CLI=0912345678~LISTA=VIP~PLC=ABC1234
14. FusionBridge responde PRESET_SENT.
    Wizard muestra "✅ Autorizado. Puede volver al inicio."
    Dashboard: Lado A del Surtidor 1 cambia a 🟡 Autorizado.
15. Despachador vuelve al dashboard. Puede atender otras ventas.
    El dashboard muestra el estado del Lado A en tiempo real.
16. Cliente levanta pistola, carga combustible, cuelga pistola.
17. Fusion emite EVT_PUMP_NEW_TRANSACTION: SA=185, VO=42.500, AM=42.50, PU=1.100, PR=50.00.
18. FusionBridge hace handshake (Lock → ClearSale → Unlock) y notifica a PowerFin.
    PowerFin emite factura SRI: 001-001-000001234.
19. SSE emite SALE_COMPLETED. Dashboard cambia Lado A a:
    🟢 "Pendiente de Cobro — $42.50 — Inició: Juan".
    La manguera ya está libre para otra venta.
20. CUALQUIER despachador (Juan, María, etc.) ve "Pendiente de Cobro" y puede tocar.
    Si María toca: wizard muestra resumen del despacho.
21. Wizard muestra resumen:
    - Total: $42.50, Volumen: 42.500 L, Preset: $50.00, Vuelto: $7.50.
    - Cliente: Juan Pérez · ABC-1234.
    - Factura: 001-001-000001234.
22. María selecciona forma de pago: "Efectivo".
23. María presiona "Confirmar — Cobrar $42.50".
24. POS envía POST /api/pos/dispatches/OV-001/collect:
    { collected_by_shift_id: turno_de_María, payment_method: "EFECTIVO",
      collected_amount: 42.50, change_amount: 7.50 }
25. PowerFin actualiza shift_id de la orden al turno de María.
    El dinero ($42.50) va a la caja de María.
26. Política ASK: wizard muestra "¿Desea ticket?".
27. Despachador (María) presiona SÍ. Ticket impreso.
28. Wizard muestra "✅ Venta completada" con botón "Nueva Venta".
29. María toca "Nueva Venta" → vuelve al dashboard.
```

---

## Escenario 2 — Placa con datos incompletos (falta email)

```
1-5. Igual que Escenario 1.
6. PowerFin responde: vehicle_found=true, incomplete_fields=["email"].
7. Wizard muestra CustomerForm (modo: incomplete).
   - "El cliente no tiene email registrado. Es necesario para la factura."
   - Campo email requerido. Datos de identificación precargados, no editables.
8. Despachador ingresa "jperez@email.com" y presiona "Continuar".
9. POS envía datos a PowerFin (actualiza email del cliente).
10. Wizard muestra BillingConfirmation con los datos ya completos.
11-29. Igual que Escenario 1 desde paso 8.

Variante 2a — Despachador cancela el formulario:
8. Despachador presiona "Cancelar" en CustomerForm.
9. Vuelve al paso 4 (input de placa). Puede ingresar otra placa.
```

---

## Escenario 3 — Placa no encontrada, persona facturadora SÍ existe

```
1-5. Igual que Escenario 1.
6. PowerFin responde: vehicle_found=false, owner=null.
7. Wizard muestra: "❌ Vehículo no encontrado".
   Subtítulo: "Ingrese identificación para buscar en PowerFin".
8. Despachador selecciona tipo Cédula, ingresa "0912345678", presiona Buscar.
9. PowerFin responde: cliente encontrado (Juan Carlos Pérez, VIP).
10. Wizard muestra BillingConfirmation: "¿Facturar a Juan Carlos Pérez (VIP)?"
11-29. Igual que Escenario 1 desde paso 8.
```

---

## Escenario 4 — Placa no encontrada, persona facturadora NO existe (registro nuevo)

```
1-6. Igual que Escenario 3 (placa no encontrada).
7. Wizard muestra: "❌ Vehículo no encontrado".
8. Despachador selecciona Cédula, ingresa "0102030405", presiona Buscar.
9. PowerFin responde: 404 CUSTOMER_NOT_FOUND.
10. Wizard muestra CustomerForm (modo: registration).
    - Campos requeridos: Tipo ID, Número ID, Nombre, Email.
    - Placa precargada del paso 5.
11. Despachador llena todos los campos y presiona "Continuar".
12. POS registra nuevo cliente en PowerFin (POST /customers).
13. PowerFin responde: customer_id=0102030405, price_list=STANDARD.
14. Wizard muestra BillingConfirmation con los datos recién registrados.
15-29. Igual que Escenario 1 desde paso 8 (precio STANDARD).

Variante 4a — Despachador cancela el registro:
11. Despachador presiona "Cancelar" en CustomerForm.
12. Vuelve al paso 7 (búsqueda por ID). Puede intentar otra identificación.

Variante 4b — Despachador presiona "Volver" en búsqueda por ID:
8. Despachador presiona "Volver".
9. Vuelve al paso 4 (input de placa). Puede ingresar otra placa.
```

---

## Escenario 5 — Cambio de persona facturadora

```
1-7. Igual que Escenario 1 (datos completos, se muestra BillingConfirmation).
8. BillingConfirmation muestra: "¿Facturar a Juan Carlos Pérez (VIP)?"
9. Despachador presiona "Cambiar" (quiere facturar a otra persona).
10. Wizard muestra búsqueda por ID con título: "¿Facturar a otra persona?"
    Subtítulo: "Ingrese la identificación para la factura".
11. Despachador selecciona RUC, ingresa "1790012345001", presiona Buscar.
12. PowerFin responde: Transportes Andinos S.A. (STANDARD).
13. Wizard muestra BillingConfirmation con Transportes Andinos.
    El precio cambia de $1.100 (VIP) a $1.500 (STANDARD).
14. Despachador presiona "Correcto".
15-29. Igual que Escenario 1 desde paso 9, con precio STANDARD.

Variante 5a — La nueva persona facturadora no existe:
11. Despachador ingresa RUC que no existe.
12. PowerFin responde: 404 CUSTOMER_NOT_FOUND.
13. Wizard muestra CustomerForm (modo: registration).
14. Flujo continúa como Escenario 4 desde paso 10.
```

---

## Escenario 6 — Venta sin identificar (Consumidor Final)

```
1-4. Igual que Escenario 1 (seleccionar lado y pistola).
5. Despachador NO ingresa placa. Presiona "Sin identificar (Consumidor Final)".
6. POS asume price_list=STANDARD, sin cliente asociado.
7-8. Wizard muestra selector de tipo de preset (Monto/Galones).
9. Despachador ingresa $20 por monto y presiona "Autorizar Despacho".
10. POS crea orden con customer_id=FINAL.
11-19. Flujo normal de autorización, despacho, pendiente de cobro.
    Dashboard muestra "Pendiente de Cobro — $17.00 — Consumidor Final".
20. Cualquier despachador toca y cobra (igual que Escenario 1).
21-29. Cobro e impresión normales. Ticket dice "Consumidor Final".
    No se emite factura con datos fiscales.
```

---

## Escenario 7 — Dos vehículos cargando simultáneamente en el mismo surtidor

```
1. Despachador Carlos toca Lado A del Surtidor 1.
2. Flujo normal: selecciona pistola, busca placa, autoriza $30.
3. Dashboard: Lado A → 🟡 Autorizado — Carlos $30.00.
4. Carlos vuelve al dashboard.
5. Mientras cliente de Carlos carga en Lado A...
6. Despachadora María toca Lado B del Surtidor 1 (estado: Disponible).
7. Flujo normal: selecciona Diesel, busca placa, autoriza $50.
8. Dashboard: Lado B → 🟡 Autorizado — María $50.00.
9. Ambos lados despachan simultáneamente. Estados independientes.
10. Lado A termina primero → Dashboard: 🟢 "Pendiente de Cobro — $25.50".
11. Lado B termina después → Dashboard: 🟢 "Pendiente de Cobro — $42.50".
12. Carlos (u otro despachador) cobra Lado A: dinero a caja de quien cobró.
13. María (u otro despachador) cobra Lado B: dinero a caja de quien cobró.
```

---

## Escenario 8 — Despachador atiende múltiples ventas en secuencia

```
1. Carlos autoriza venta en Surtidor 1, Lado A ($30).
2. Vuelve al dashboard. Lado A muestra 🟡 Autorizado.
3. Carlos toca Surtidor 2, Lado B (Disponible).
4. Inicia nueva venta: busca placa, autoriza $20 en Surtidor 2, Lado B.
5. Vuelve al dashboard. Ahora hay DOS lados activos:
   - Surtidor 1, Lado A: 🟠 Despachando — Carlos $30.00
   - Surtidor 2, Lado B: 🟡 Autorizado — Carlos $20.00
6. Surtidor 1, Lado A termina → 🟢 "Pendiente de Cobro — $25.50".
7. Surtidor 2, Lado B termina → 🟢 "Pendiente de Cobro — $17.00".
8. Carlos toca cada uno para cobrar, en el orden que prefiera.
9. Si Carlos está ocupado, María puede cobrar cualquiera de los dos.
   El dinero va a la caja de quien cobre (Regla 1).
```

---

## Escenario 9 — Error de autorización: manguera ocupada por otro despachador

```
1. Carlos toca Lado A del Surtidor 1 y empieza wizard.
2. Mientras Carlos busca placa, María (desde su tablet) toca el mismo Lado A
   y completa el wizard más rápido. Autoriza primero.
3. Dashboard: Lado A → 🟡 Autorizado — María $50.00.
4. Carlos termina de buscar placa y presiona "Autorizar Despacho".
5. FusionBridge responde: 409 Conflict — "Manguera ocupada por María".
6. Wizard muestra: "Esta manguera ya está siendo usada por María".
7. Carlos debe seleccionar otro lado/surtidor disponible.
```

---

## Escenario 10 — Despachador cancela un preset antes de que el cliente cargue

```
1-14. Igual que Escenario 1 (venta autorizada, preset enviado).
15. Cliente aún no ha levantado la pistola (estado AUTHORIZED).
16. Cliente cambia de opinión o pide otro grado.
17. Despachador toca el lado en el dashboard (🟡 Autorizado) → ve opción "Cancelar".
18. Despachador presiona "Cancelar preset".
19. POS envía cancelDispatch a FusionBridge → REQ_PUMP_CLEAR_PRESET.
20. FusionBridge responde OK. Manguera vuelve a IDLE.
21. POS cancela la orden en PowerFin (POST /dispatches/{id}/cancel).
22. Dashboard: Lado A vuelve a 🟢 Disponible.
```

---

## Escenario 11 — Impresora no disponible (error de impresión)

```
1-27. Igual que Escenario 1 (venta completada, se solicita ticket).
28. Impresora 192.168.1.31 no responde (apagada, desconectada, sin papel).
29. FusionBridge responde: 503 — "Printer not reachable".
30. Wizard muestra: "⚠️ Error al imprimir. [Reintentar]".
31. Despachador puede:
    a. Reintentar (si era un problema temporal).
    b. Presionar "Nueva Venta" y continuar (la venta ya está registrada).
32. El ticket se puede reimprimir luego desde el historial (futuro).

Nota: El error de impresión NUNCA bloquea la venta. El cobro ya fue registrado.
```

---

## Escenario 12 — FusionBridge o PowerFin no disponibles

### 12a — PowerFin no disponible al crear orden:
```
1-9. Igual que Escenario 1.
10. POS intenta POST /api/pos/dispatches → timeout / error de red.
11. Wizard muestra: "Error de conexión. Reintentando...".
12. POS reintenta automáticamente hasta 3 veces.
13. Si todos fallan: "No se puede crear la orden. Intente de nuevo."
14. Despachador presiona "Reintentar" o vuelve al dashboard.
```

### 12b — FusionBridge no disponible al autorizar:
```
1-10. Orden creada exitosamente en PowerFin.
11. POS intenta POST /api/dispatch/authorize → timeout / error de red.
12. Wizard muestra: "No hay conexión con los surtidores. Reintentando...".
13. Si falla: "Surtidor no disponible. La orden queda pendiente."
14. Despachador puede atender otro cliente. La orden queda en estado PENDING.
```

### 12c — Recuperación al reconectar:
```
1. FusionBridge se reconecta al Fusion.
2. FusionBridge consulta REQ_GET_PUMP_SALES para ventas ocurridas offline.
3. FusionBridge casa cada venta con su orden usando PAY_IN (OV=...).
4. Órdenes pendientes se completan automáticamente.
5. SSE notifica a los POS conectados.
6. Dashboard actualiza estados a "Pendiente de Cobro".
```

---

## Escenario 13 — Cierre de turno con ventas activas

```
1. Despachador presiona "Cerrar turno".
2. POS verifica: ¿hay órdenes en estado AUTHORIZED o FUELLING de este turno?
3. Si SÍ hay ventas activas:
   a. POS muestra: "No puede cerrar turno. Hay 2 despachos en curso."
   b. Muestra lista de surtidores y mangueras activas.
   c. Despachador debe esperar a que terminen o cancelarlas.
4. Si NO hay ventas activas pero SÍ hay "Pendiente de Cobro":
   a. POS muestra: "Hay 3 ventas pendientes de cobro. ¿Desea cerrar igual?"
   b. Si cierra sin cobrar → diferencia negativa en el cuadre.
5. Si todo está cobrado:
   a. POS muestra resumen del turno.
   b. Efectivo esperado = apertura + ventas efectivo cobradas - depósitos caja fuerte.
   c. Despachador ingresa efectivo real contado.
   d. POS muestra diferencia (debe ser ~$0.00).
   e. Despachador confirma cierre.
   f. POS envía POST /shifts/{id}/close a PowerFin.
   g. Sesión cerrada. Redirige a login.
```

---

## Escenario 14 — Depósito a caja fuerte durante el turno

```
1. Despachador ha acumulado $235 en efectivo en su caja.
2. Sistema muestra alerta en el dashboard: "⚠️ Caja: $235.00 — Deposite a caja fuerte."
3. Despachador presiona "Caja" → "Depositar".
4. Ingresa monto: $200.00. Motivo: "Depósito de seguridad".
5. POS envía POST /api/pos/safe-drops a PowerFin.
6. PowerFin registra el depósito y descuenta de la caja del turno.
7. Dashboard: caja ahora muestra $35.00.
8. Al cerrar turno, el efectivo esperado ya descuenta los depósitos.
```

---

## Escenario 15 — Supervisor fuerza cierre de turno ajeno

```
1. Despachador Carlos se fue sin cerrar turno (emergencia, olvido).
2. Supervisor inicia sesión en PowerFin ERP (no en el POS).
3. Supervisor ve turnos abiertos: Carlos — Abierto desde 06:03 (8h 15min).
4. Supervisor selecciona "Forzar cierre".
5. PowerFin verifica: ¿hay ventas activas? Si sí → fuerza cancelación o espera.
6. PowerFin cierra el turno con diferencia registrada como "CIERRE FORZADO".
7. Reporte muestra: efectivo esperado vs real, diferencia registrada.
8. Queda registro de auditoría: quién forzó el cierre, cuándo, y por qué.
```

---

## Escenario 16 — Cliente VIP vs STANDARD, precios por grado de combustible

```
Situación actual (mock):
- VIP: $1.100/L sin importar el grado.
- STANDARD: $1.500/L sin importar el grado.

Situación futura (cuando PowerFin tenga precios por grado):
- SUPER STANDARD: $1.500/L    SUPER VIP: $1.100/L
- EXTRA STANDARD: $1.300/L    EXTRA VIP: $0.950/L
- DIESEL STANDARD: $1.200/L   DIESEL VIP: $0.900/L

El precio se determina por: (cliente.price_list × grado_seleccionado).
PowerFin es la única fuente de verdad del precio.
El POS consulta GET /api/pos/prices?customerId=X&gradeId=SUPER.
```

---

## Escenario 17 — Cliente con crédito activo

```
1-9. Igual que Escenario 1.
10. Al seleccionar forma de pago, aparece opción "Crédito".
11. Despachador selecciona "Crédito".
12. POS consulta límite de crédito disponible del cliente.
13. Si el monto ≤ crédito disponible → se autoriza normalmente.
14. Si el monto > crédito disponible → mensaje: "Crédito insuficiente. Disponible: $300.00".
15. PowerFin registra la venta como crédito y descuenta del saldo.
```

---

## Escenario 18 — Validaciones de placa

```
1. Despachador ingresa placa en el input.
2. Reglas de validación:
   a. Menos de 3 caracteres → botón Buscar deshabilitado.
   b. Formato con guión "ABC-1234" → se normaliza a "ABC1234" antes de enviar.
   c. Formato sin guión "ABC1234" → se envía tal cual.
   d. Solo números "1234" → se permite buscar (algunas placas son solo numéricas).
   e. Caracteres especiales → se limpian (solo letras y números).
   f. Mínimo 3, máximo 10 caracteres después de normalizar.
3. La normalización ocurre en el frontend antes de llamar a lookupVehicle.
```

---

## Escenario 19 — Preset: Monto vs Galones

```
El despachador SIEMPRE elige el tipo de preset antes de ingresar el valor:

Opción "Por Monto":
  - Campo: "$ _______"
  - Botones rápidos: $5, $10, $20, $50, $100
  - Opción "Llenar tanque" (VA=FULL)
  - Estimación: litros = monto ÷ precio_unitario
  - Envía: TY=MONEY, VA=50.00

Opción "Por Galones":
  - Campo: "_______ galones"
  - Botones rápidos: 1, 2, 5, 10, 20 gal
  - Estimación: total = galones × precio_unitario
  - Envía: TY=VOLUME, VA=10.00

El tipo seleccionado determina:
  - preset_type en la orden de PowerFin
  - TY en el comando REQ_PUMP_PRESET al Fusion
  - Qué campo se muestra para ingresar el valor
```

---

## Escenario 20 — Recarga de página durante una venta

```
1. Despachador está en el wizard de venta.
2. Por accidente recarga la página (F5) o se queda sin batería.
3. Al volver a abrir el POS:
   a. Verifica si hay sesión activa (token en localStorage).
   b. Verifica si hay turno activo (shift en localStorage o consulta a PowerFin).
   c. Reconstruye el estado desde pendingOrders (en memoria → se pierde).
   d. Consulta estado de surtidores vía polling.
4. Si la venta seguía en curso:
   a. El polling muestra la manguera en estado AUTHORIZED/FUELLING.
   b. Despachador toca el lado → ve el progreso o puede cancelar.
5. Si la venta ya terminó:
   a. El polling detecta IDLE en la manguera.
   b. Pero el pendingOrder se perdió (estaba en memoria). → PROBLEMA.
   c. SOLUCIÓN: pendingOrders debe persistirse en localStorage.
   d. SOLUCIÓN: consultar a PowerFin órdenes pendientes del turno activo.
```

---

## Escenario 21 — Múltiples despachadores viendo el mismo surtidor

```
1. Carlos y María tienen sus tablets con el POS abierto.
2. Ambos ven el mismo Surtidor 1, Lado A en estado Disponible.
3. Carlos toca Lado A primero → inicia wizard de venta.
4. María también toca Lado A → inicia wizard de venta.
5. Carlos llega primero a "Autorizar Despacho" → éxito, manguera en AUTHORIZED.
6. María llega después a "Autorizar Despacho" → 409 Conflict.
7. María ve mensaje: "Manguera ocupada por Carlos".
8. María debe seleccionar otro lado/surtidor.

Nota: Si la venta de Carlos pasa a "Pendiente de Cobro", María SÍ puede
tocar y cobrar. El dinero va a la caja de María (Regla 1).
```

---

## Escenario 22 — Despachador A autoriza, Despachador B cobra

```
1. Juan inicia venta en Surtidor 1, Lado A. Flujo normal hasta autorizar.
2. Orden creada con shift_id temporal de Juan.
3. Juan vuelve al dashboard. Puede atender otras ventas.
4. Cliente carga combustible. Venta se completa.
5. Dashboard muestra: 🟢 "Pendiente de Cobro — $42.50 — Inició: Juan".
6. Juan está ocupado atendiendo otros clientes.
7. María ve "Pendiente de Cobro" en Surtidor 1, Lado A.
8. María toca el lado → wizard muestra resumen del despacho.
9. María selecciona "Efectivo", presiona "Confirmar — Cobrar $42.50".
10. POS envía POST /api/pos/dispatches/OV-001/collect:
    { collected_by_shift_id: turno_de_María, payment_method: "EFECTIVO",
      collected_amount: 42.50, change_amount: 7.50 }
11. PowerFin actualiza shift_id: de Juan → María.
12. El dinero ($42.50) va a la caja de María.
13. Al cerrar turno:
    - Juan: esta venta NO aparece en su cuadre.
    - María: esta venta SÍ aparece en su cuadre.
14. María da vuelto ($7.50) al cliente de su propia caja.
```

---

## Escenario 23 — Múltiples ventas pendientes de cobro simultáneas

```
1. Carlos autoriza 3 ventas en 3 lados distintos durante hora pico.
2. Las 3 se completan casi al mismo tiempo.
3. Dashboard muestra:
   - Surtidor 1, Lado A: 🟢 Pendiente de Cobro — $42.50
   - Surtidor 1, Lado B: 🟢 Pendiente de Cobro — $18.00
   - Surtidor 2, Lado A: 🟢 Pendiente de Cobro — $55.00
4. Carlos empieza a cobrar Lado A del Surtidor 1.
5. Mientras tanto, María ve los otros dos pendientes y cobra Surtidor 2, Lado A.
6. Otro despachador, Pedro, cobra Surtidor 1, Lado B.
7. Cada venta queda en el turno de quien la cobró.
8. Las cajas se cuadran independientemente al cerrar turno.
```

---

## Resumen de estados del dashboard por manguera

| Estado | Color | Significado | Acción al tocar |
|--------|-------|-------------|-----------------|
| Disponible | 🟢 Verde | Libre para vender | Iniciar wizard de venta |
| Llamando | 🔵 Azul | Cliente levantó pistola sin autorizar | Ver estado |
| Autorizado | 🟡 Amarillo | Preset enviado, esperando que levanten pistola | Ver detalle / Cancelar preset |
| Despachando | 🟠 Naranja | Cliente cargando combustible | Ver estado |
| Pausado | 🟣 Morado | Despacho pausado | Ver estado |
| Pendiente de Cobro | 🟢 Verde + $ | Venta completada, factura emitida, sin cobrar | Cobrar (cualquier despachador) |
| Error | 🔴 Rojo | Error en surtidor | No disponible |
| Cerrado | ⚫ Gris | Surtidor cerrado | No disponible |

---

## Resumen de pasos del wizard de venta

```
1. SELECCIONAR LADO       → Despachador toca Lado A o B de un surtidor disponible.
2. SELECCIONAR PISTOLA    → Elige el grado de combustible (Super, Extra, Diesel).
                            Si el lado tiene 1 sola pistola, se salta este paso.
3. BUSCAR PLACA           → Ingresa placa del vehículo y presiona Buscar.
                            Opción: "Sin identificar" para Consumidor Final.
4a. DATOS COMPLETOS       → BillingConfirmation: confirma o cambia facturador.
4b. DATOS INCOMPLETOS     → CustomerForm (incomplete): completa campos faltantes.
4c. PLACA NO ENCONTRADA   → Búsqueda por cédula/RUC.
4d. ID NO ENCONTRADO      → CustomerForm (registration): registra nuevo cliente.
4e. CAMBIAR FACTURADOR    → Búsqueda por cédula/RUC de otra persona.
5. TIPO DE PRESET         → "Por Monto" ($) o "Por Galones" (galones).
6. INGRESAR VALOR         → Monto o galones con botones rápidos. Estimación en tiempo real.
7. AUTORIZAR              → Crear orden en PowerFin + enviar preset a FusionBridge.
8. VOLVER AL DASHBOARD    → El despachador puede atender otras ventas.
9. ESPERAR COMPLETADO     → El dashboard muestra el estado en tiempo real.
10. COBRAR                → CUALQUIER despachador toca "Pendiente de Cobro".
                            Selecciona forma de pago y confirma.
11. IMPRIMIR TICKET       → Según política: ALWAYS (automático), ASK (pregunta), NEVER (no).
12. NUEVA VENTA           → Volver al dashboard.
```
