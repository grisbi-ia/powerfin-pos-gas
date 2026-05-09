# Wayne Fusion/Synergy — Protocolo de Integración

## Contexto

El Wayne Synergy (también llamado Wayne Fusion FCC) es una consola que actúa como
gateway entre los dispensadores de combustible y sistemas externos (POS, ERP).

PowerFinPos-Gas se conecta al Synergy vía TCP y usa el **Fusion Native Protocol**
(protocolo propietario de Wayne/Dover Fueling Solutions).

**Referencia oficial:** "Dresser Wayne Fusion 3rd Party Interface — Message Routing System V1.33"

---

## Datos de conexión GASOLINERA (validados en pruebas reales)

```
IP del Synergy:   192.168.1.20
Puerto TCP:       3011
Firmware:         Rel-5.19.1
OS del Synergy:   Windows
Hardware:         V2
MAC:              68:1d:ef:31:53:86
Cifrado:          Sin cifrado (crypt field = '5')
Keep-alive:       ECHO cada 120 segundos (timeout: 360 segundos)
```

---

## Formato del mensaje

```
<len>|<crypt>|<version>|<user_id>|<msg_type>|<event>|<destination>|<origin>|<params>|^
```

| Campo         | Tamaño    | Descripción                                        |
| ------------- | --------- | -------------------------------------------------- |
| `len`         | 5 dígitos | Longitud desde `<version>` hasta `^` inclusive     |
| `crypt`       | 1 byte    | `5` = sin cifrado, `6` = cifrado XOR               |
| `version`     | 1 byte    | Siempre `2`                                        |
| `user_id`     | variable  | Dejar vacío — Fusion lo completa                   |
| `msg_type`    | variable  | `POST`, `SUBSCRIBE`, `UNSUBSCRIBE`, `ECHO`, `EXIT` |
| `event`       | variable  | Nombre del evento o request                        |
| `destination` | variable  | `IP:puerto` o vacío                                |
| `origin`      | variable  | Dejar vacío — Fusion lo completa                   |
| `params`      | variable  | `CAMPO=VALOR\|CAMPO=VALOR`                         |
| `^`           | 1 byte    | Terminador de mensaje                              |

### Cómo calcular el campo `len`

```java
String body = "2||POST|" + eventType + "|" + destination + "|" + origin + "|" + params + "|^";
int len = body.length();
String mensaje = String.format("%05d|5|%s", len, body);
```

### Ejemplo real validado

```
// Solicitar estado de todos los surtidores
Enviado:   00035|5|2||POST|REQ_PUMP_STATUS_ID_000||||^
Recibido:  00088|5|2|GUEST|POST|EVT_PUMP_STATUS_CHANGE_ID_001|192.168.1.100:35378|127.0.0.1:50602|SU=|ST=CLOSED|PR=0.00|HN=2|__PP=1|^
```

---

## Tipos de mensajes (msg_type)

| Tipo          | Descripción                          |
| ------------- | ------------------------------------ |
| `POST`        | Enviar request o evento dirigido     |
| `SUBSCRIBE`   | Suscribirse a eventos no solicitados |
| `UNSUBSCRIBE` | Cancelar suscripción                 |
| `ECHO`        | Keep-alive — se devuelve idéntico    |
| `EXIT`        | Cerrar conexión limpiamente          |

---

## ECHO — Keep-alive

```
Enviar cada 120 segundos si no hay actividad.
Si Fusion no detecta actividad en 360 segundos → cierra la conexión.

Mensaje:   00012|5|2||ECHO||||^
Respuesta: 00031|5|2||ECHO||192.168.1.100:PUERTO||^
```

---

## Suscripciones — Wildcard

```java
// Suscribirse a todos los cambios de estado de todos los surtidores
"SUBSCRIBE|EVT_PUMP_STATUS_CHANGE_ID_*"

// Suscribirse a todos los eventos de surtidores
"SUBSCRIBE|EVT_PUMP_*"

// Suscribirse a absolutamente todo
"SUBSCRIBE|ALL"
```

---

## Suscripciones obligatorias al iniciar

```java
// El FusionTcpClient debe enviar estas suscripciones al conectar:
private static final String[] SUSCRIPCIONES_OBLIGATORIAS = {
    "EVT_PUMP_STATUS_CHANGE_ID_000",   // cambios de estado todos los surtidores
    "EVT_PUMP_NEW_TRANSACTION",         // nueva transacción completada
    "EVT_NEW_CONFIG_APPLIED",           // cambio de configuración
    "EVT_PAYMENT_SALE_CLEARED",         // venta marcada como pagada
    "EVT_PAYMENT_ATTRIBUTES_CHANGE",    // cambio de atributos de pago
    "EVT_PAYMENT_TRANSACTION_LOCK",     // venta bloqueada por otro módulo
    "EVT_NEW_PRICE_CHANGE_APPLIED"      // cambio de precios aplicado
};

// Suscripciones opcionales
private static final String[] SUSCRIPCIONES_OPCIONALES = {
    "EVT_PUMP_DELIVERY_PROGRESS_ID_000", // progreso de despacho en tiempo real
    "EVT_PUMP_TOTALIZER_UPDATE_ID_000",  // actualización de totalizadores
    "EVT_PRICES_APPROVAL_STATUS_CHANGE"  // cambio de estado de aprobación de precios
};
```

---

## Eventos del Fusion (mensajes que Fusion envía al POS)

### EVT_PUMP_STATUS_CHANGE_ID_XXX

Emitido cada vez que un surtidor cambia de estado.

| Parámetro | Descripción                                                                                                                   |
| --------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `ST`      | Estado: `CLOSED`, `ERROR`, `IDLE`, `CALLING`, `AUTHORIZED`, `STARTING`, `FUELLING`, `PAUSED`                                  |
| `SU`      | Sub-estado: `IDLE`, `MONEY_PRESET`, `VOLUME_PRESET`, `MONEY_PREPAY`, `AUTHORIZATION`, `STOPPED`, `CALL_WRONG`, `HOSE_SEL_REQ` |
| `HO`      | Número de pistola en uso (si aplica)                                                                                          |
| `GR`      | Número de grade/combustible                                                                                                   |
| `PAY_AL`  | `ON` si hay alarma de pago (venta sin cobrar por timeout)                                                                     |
| `PAY_PID` | Prepay ID                                                                                                                     |
| `PAY_IN`  | Información de pago enviada por el POS                                                                                        |
| `PR`      | Monto del preset (si hay preset activo)                                                                                       |
| `PR_HO`   | Pistolas del preset                                                                                                           |
| `PR_GR`   | Grades del preset                                                                                                             |

### Diagrama de estados del surtidor

```
CLOSED ──OPEN──► ERROR
                   │ (online)
                   ▼
                  IDLE ◄──── cuelga pistola
                   │
          ┌────────┼────────┐
          │                 │
    levanta pistola    Authorize/Preset
          ▼                 ▼
       CALLING ──────► AUTHORIZED
                           │
                     levanta pistola
                           ▼
                        STARTING
                           │
                        FUELLING ──Pause──► PAUSED
                           │                  │
                     cuelga pistola      Clear_Pause
                           ▼                  │
                          IDLE ◄──────────────┘
```

### EVT_PUMP_NEW_TRANSACTION

Emitido cuando una transacción se completa (pistola colgada).

| Parámetro | Descripción                                                             |
| --------- | ----------------------------------------------------------------------- |
| `SA`      | ID único de venta en Fusion (único de por vida)                         |
| `PM`      | Número de surtidor                                                      |
| `HO`      | Número de pistola                                                       |
| `GR`      | Número de grade/combustible                                             |
| `VO`      | Volumen despachado (3 decimales)                                        |
| `AM`      | Monto cobrado (3 decimales)                                             |
| `PU`      | Precio por unidad PPU (3 decimales)                                     |
| `PR`      | Monto preset original (para calcular vuelto: `vuelto = PR - AM`)        |
| `TY`      | Tipo: `0`=sin control, `1`=regular, `2`=prueba surtidor                 |
| `DA`      | Fecha fin (YYYYMMDD)                                                    |
| `TI`      | Hora fin (HHMMSS)                                                       |
| `SDA`     | Fecha inicio (YYYYMMDD)                                                 |
| `STI`     | Hora inicio (HHMMSS)                                                    |
| `LV`      | Nivel de precio                                                         |
| `PAY_TY`  | Tipo de pago enviado por el POS                                         |
| `PAY_IN`  | Info de pago libre enviada por el POS (aquí viaja el ordenId)           |
| `IVO`     | Totalizador de volumen inicial                                          |
| `FVO`     | Totalizador de volumen final                                            |
| `IM`      | Totalizador monetario inicial                                           |
| `FM`      | Totalizador monetario final                                             |
| `FCR`     | Razón de fin: `NormalCompletion`, `ZeroFilling`, `AuthorizationTimeout` |
| `LID`     | Lock ID si la venta está bloqueada                                      |
| `SID`     | Shift ID (turno)                                                        |
| `ATCVO`   | Volumen compensado por temperatura (si disponible)                      |
| `AVGTM`   | Temperatura promedio del despacho                                       |

### EVT_PUMP_DELIVERY_PROGRESS_ID_XXX

Emitido mientras el surtidor está despachando (en tiempo real).

| Parámetro | Descripción                                         |
| --------- | --------------------------------------------------- |
| `AM`      | Monto acumulado hasta ese momento                   |
| `VO`      | Volumen acumulado hasta ese momento                 |
| `AMS`     | Monto a mostrar (invertido si es preset por monto)  |
| `PU`      | PPU en uso                                          |
| `HO`      | Pistola                                             |
| `TS`      | Timestamp: `SSSSSSS.MMM` (segundos desde 1970 + ms) |

### EVT_PAYMENT_TRANSACTION_LOCK

Emitido cuando otro módulo bloquea una transacción.

| Parámetro | Descripción                         |
| --------- | ----------------------------------- |
| `SA`      | ID de venta bloqueada               |
| `LID`     | Lock ID (vacío si fue desbloqueada) |

### EVT_NEW_PRICE_CHANGE_APPLIED

Emitido cuando cambia el precio en el Fusion.

| Parámetro | Descripción    |
| --------- | -------------- |
| `RC`      | `OK` o `ERROR` |

---

## Requests del POS hacia Fusion

### REQ_PUMP_STATUS_ID_XXX — Consultar estado

```
// Estado de un surtidor específico
POST|REQ_PUMP_STATUS_ID_001||||^

// Estado de TODOS los surtidores
POST|REQ_PUMP_STATUS_ID_000||||^
```

Respuesta: uno o más `EVT_PUMP_STATUS_CHANGE_ID_XXX`

---

### REQ_PUMP_PRESET_ID_XXX — Autorizar despacho (el más importante)

```
POST|REQ_PUMP_PRESET_ID_001|||
  TY=MONEY|          // MONEY o VOLUME
  VA=50.00|          // monto o volumen
  HO=1@1.100|        // pistola 1 con precio especial $1.100
  PAY_TY=EFECTIVO|   // tipo de pago
  PAY_IN=OV=OV-001~CLI=0912345678~LISTA=VIP|  // datos fiscales
  FTS=YES|           // forzar envío aunque esté en IDLE
  ^
```

**Parámetros clave:**

| Parámetro | Descripción                                                               |
| --------- | ------------------------------------------------------------------------- |
| `TY`      | `MONEY` (preset por monto) o `VOLUME` (preset por volumen)                |
| `VA`      | Valor del preset. `FULL` para llenar el tanque                            |
| `HO`      | Lista de pistolas autorizadas. Formato: `HO=1` o `HO=1@PRECIO,2,4@PRECIO` |
| `GR`      | Lista de grades autorizados (exclusivo con HO)                            |
| `PAY_TY`  | Tipo de pago — string libre (EFECTIVO, TARJETA, QR, CREDITO, etc.)        |
| `PAY_PID` | Prepay ID establecido por el POS                                          |
| `PAY_IN`  | Info de pago libre — formato `CAMPO=VALOR~CAMPO=VALOR`                    |
| `OS`      | Estado original conocido del surtidor (anti-race condition)               |
| `LID`     | Lock ID para bloquear la transacción                                      |
| `LM`      | Modo de lock: `NORMAL` (default) o `ONCE`                                 |
| `SDN`     | Slow Down: litros antes del preset para reducir caudal                    |
| `FTS`     | `YES` para forzar envío en estado IDLE                                    |

**Formato de precio diferencial por pistola:**

```
HO=1@1.100,2,4@0.990
// Pistola 1: $1.100/litro (VIP)
// Pistola 2: precio estándar del Fusion
// Pistola 4: $0.990/litro (empleado)
```

**Formato del campo PAY_IN (datos que viajan con la transacción):**

```
PAY_IN=OV=OV-20240421-143022-001~CLI=0912345678~LISTA=VIP~PLC=ABC-1234

// OV    = ID de orden en PowerFinPos-Gas (CRÍTICO para recuperación ante fallos)
// CLI   = Cédula/RUC del cliente
// LISTA = Lista de precio aplicada
// PLC   = Placa del vehículo
```

**IMPORTANTE:** El valor de `OV` en `PAY_IN` es la clave de reconciliación.
Si FusionTcpClient cae y se reconecta, usa este campo para encontrar
la venta en `REQ_GET_PUMP_SALES` y asociarla a la orden correcta.

**Respuesta:** No hay respuesta directa. Confirmar con `EVT_PUMP_STATUS_CHANGE` → `ST=AUTHORIZED`.

---

### REQ_PUMP_CLEAR_PRESET_ID_XXX — Cancelar preset

```
POST|REQ_PUMP_CLEAR_PRESET_ID_001||||^
```

Solo funciona si el surtidor está en `ST=IDLE + SU=PRESET`.

---

### REQ_PUMP_AUTH_ID_XXX — Autorización simple (sin monto preset)

```
POST|REQ_PUMP_AUTH_ID_001|||HO=1|^
```

Autoriza el surtidor sin limite de monto. Menos usado que preset.

---

### REQ_PUMP_STOP_ID_XXX — Detener surtidor

```
// Detener surtidor específico
POST|REQ_PUMP_STOP_ID_001|||PA=1|^

// Detener TODOS los surtidores
POST|REQ_PUMP_STOP_ID_000|||PA=1|^

// PA=1: si está despachando, pausar primero
// PA=0: esperar que termine la transacción actual
```

---

### REQ_PUMP_CLEAR_STOP_ID_XXX — Liberar surtidor detenido

```
POST|REQ_PUMP_CLEAR_STOP_ID_001||||^
POST|REQ_PUMP_CLEAR_STOP_ID_000||||^  // todos
```

---

### REQ_PUMP_PAUSE_ID_XXX — Pausar despacho en curso

```
POST|REQ_PUMP_PAUSE_ID_001||||^
```

Solo funciona si el surtidor está en `STARTING` o `FUELLING`.

---

### REQ_PUMP_REAUTH_ID_XXX — Reanudar despacho pausado

```
POST|REQ_PUMP_REAUTH_ID_001||||^
```

Solo funciona si el surtidor está en `STOPPED`.

---

### REQ_PUMP_OPEN_ID_XXX — Abrir surtidor (CLOSED → ERROR → IDLE)

```
POST|REQ_PUMP_OPEN_ID_001||||^
POST|REQ_PUMP_OPEN_ID_000||||^  // todos
```

Necesario al arrancar si el surtidor está en CLOSED.

---

### REQ_PAYMENT_TRANSACTION_LOCK — Bloquear venta

```
POST|REQ_PAYMENT_TRANSACTION_LOCK|||SA=185|LID=OV-001||^
```

Bloquea la venta para que otro módulo no pueda pagarla simultáneamente.

| Parámetro | Descripción                                              |
| --------- | -------------------------------------------------------- |
| `SA`      | ID de venta a bloquear                                   |
| `LID`     | Lock ID establecido por el POS (usar el ordenId)         |
| `TMO`     | Timeout de auto-desbloqueo en segundos (recomendado: 10) |

---

### REQ_PAYMENT_CLEAR_SALE — Marcar venta como pagada

```
POST|REQ_PAYMENT_CLEAR_SALE|||
  SA=185|
  TY=EFECTIVO|
  AT=InvoicedBy=POWERFIN~Factura=001-001-000001|
  LID=OV-001|
  ^
```

| Parámetro | Descripción                                     |
| --------- | ----------------------------------------------- |
| `SA`      | ID de venta                                     |
| `TY`      | Tipo de pago (string libre)                     |
| `AT`      | Atributos adicionales `CAMPO=VALOR~CAMPO=VALOR` |
| `LID`     | Lock ID (debe coincidir con el usado en LOCK)   |
| `PM`      | Número de surtidor (opcional)                   |

**Formato del campo AT:**

```
AT=InvoicedBy=POWERFIN~Factura=001-001-000001~RFC=EFECTIVO

// Para campo oculto (no aparece en reportes Fusion):
AT=InvoicedBy=POWERFIN~#Procesado=SI

// Para campo persistente (no se borra si cambia el tipo de venta):
AT=InvoicedBy=POWERFIN~$PuntosLoyalty=100
```

---

### REQ_PAYMENT_TRANSACTION_UNLOCK — Desbloquear venta

```
POST|REQ_PAYMENT_TRANSACTION_UNLOCK|||SA=185|LID=OV-001||^
```

---

### REQ_PAYMENT_UNPAY_SALE — Marcar venta como impaga (reversión)

```
POST|REQ_PAYMENT_UNPAY_SALE|||SA=185||^
```

---

### REQ_PAYMENT_PUMP_TEST — Marcar venta como prueba/recirculación

```
// Sin retorno al tanque
POST|REQ_PAYMENT_PUMP_TEST|||SA=196||^

// Con retorno al tanque 1
POST|REQ_PAYMENT_PUMP_TEST|||SA=195|TANK=1||^
```

---

### REQ_GET_SALE_DETAIL — Obtener detalle de una venta

```
POST|REQ_GET_SALE_DETAIL|Forecourt||SID=185||^
```

Respuesta: `RES_GET_SALE_DETAIL` con todos los campos de la venta.
Útil para recovery: consultar ventas que ocurrieron mientras el POS estaba caído.

---

### REQ_GET_PUMP_SALES — Obtener últimas ventas de un surtidor

```
POST|REQ_GET_PUMP_SALES|Forecourt||PM=1|QT=5||^
```

Retorna las últimas 5 ventas del surtidor 1 (máximo 10 por request).
**Clave para el RecoveryService.**

---

### REQ_FCRT_GET_GRAL_CONFIG — Configuración general del site

```
POST|REQ_FCRT_GET_GRAL_CONFIG|Forecourt Controller||||^
```

Respuesta incluye: `SNR`, `SNA`, `SLNA`, `MUA`, `MUD`, `DF`, `DCP`, `DCM`, `DCV`.

---

### REQ_FCRT_PUMPS_CONFIG — Configuración de surtidores

```
POST|REQ_FCRT_PUMPS_CONFIG|Forecourt Controller||PC=POWERFIN|MID=001|^
```

Respuesta incluye para cada surtidor: `PxxxHOSES`, `PxxxHyGRADE`, `PxxxHyPRICE`, `PxxxHyTNKS`.

---

### REQ_FCRT_GRADES_CONFIG — Configuración de combustibles

```
POST|REQ_FCRT_GRADES_CONFIG|Forecourt Controller||||^
```

Respuesta incluye: `GRADES`, `GxxxDES`, `GxxxGNR`, `GxxxLzz` (precios por nivel).

---

### REQ_FCRT_TANK_CONFIG — Configuración de tanques

```
POST|REQ_FCRT_TANK_CONFIG|Forecourt Controller||||^
```

---

### REQ_SHIFT_CLOSE_PERIOD — Cierre de turno/día/mes/año

```
// Cierre de turno
POST|REQ_SHIFT_CLOSE_PERIOD|Shifts Add In||PT=S||^

// Cierre de día
POST|REQ_SHIFT_CLOSE_PERIOD|Shifts Add In||PT=D||^

// PT: S=Shift, D=Day, M=Month, Y=Year
```

**IMPORTANTE:** No se puede cerrar un turno con ventas impagas.

---

### REQ_PRICES_SET_NEW_PRICE_CHANGE — Cambiar precios desde el POS

```
POST|REQ_PRICES_SET_NEW_PRICE_CHANGE|Price Change Add In||
  QTY=1|
  G01NR=1|
  G01LV=1|
  G01PR=1.150|
  ^
```

Permite que PowerFinPos-Gas actualice los precios en el Fusion.

---

### REQ_GET_FUSION_VERSION — Versión del firmware

```
POST|REQ_GET_FUSION_VERSION|Message Router||||^
```

Respuesta: `OS`, `HWV`, `BIN`, `MAC`.

---

## Flujo completo de una venta

### Caso 1: Venta postpago (Full Service)

```
1. SUSCRIPCIÓN (al iniciar):
   SUBSCRIBE|EVT_PUMP_STATUS_CHANGE_ID_000
   SUBSCRIBE|EVT_PUMP_NEW_TRANSACTION

2. CLIENTE LEVANTA PISTOLA (Fusion envía):
   EVT_PUMP_STATUS_CHANGE_ID_001 → ST=CALLING, HO=1

3. POS AUTORIZA (opcional en Full Service, requerido en Self Service):
   POST|REQ_PUMP_AUTH_ID_001||||^
   ← EVT_PUMP_STATUS_CHANGE_ID_001 → ST=AUTHORIZED

4. DESPACHO (Fusion envía progreso):
   EVT_PUMP_STATUS_CHANGE_ID_001 → ST=FUELLING
   EVT_PUMP_DELIVERY_PROGRESS_ID_001 → AM=x, VO=y (múltiples veces)

5. FIN DEL DESPACHO (cliente cuelga pistola):
   EVT_PUMP_STATUS_CHANGE_ID_001 → ST=IDLE
   EVT_PUMP_NEW_TRANSACTION → SA=185, VO=45.455, AM=50.00, PU=1.100

6. POS COBRA (handshake de pago):
   POST|REQ_PAYMENT_TRANSACTION_LOCK|||SA=185|LID=OV-001|TMO=10|^
   ← RES_PAYMENT_TRANSACTION_LOCK → ST=OK

   POST|REQ_PAYMENT_CLEAR_SALE|||SA=185|TY=EFECTIVO|LID=OV-001|^
   ← RES_PAYMENT_CLEAR_SALE → ST=OK

   POST|REQ_PAYMENT_TRANSACTION_UNLOCK|||SA=185|LID=OV-001|^
   ← RES_PAYMENT_TRANSACTION_UNLOCK → ST=OK
```

### Caso 2: Venta prepagada (Self Service)

```
1. POS ENVÍA PRESET CON PAGO INCLUIDO:
   POST|REQ_PUMP_PRESET_ID_001|||
     VA=50.00|HO=1@1.100|TY=MONEY|
     PAY_TY=TARJETA|
     PAY_IN=OV=OV-001~CLI=0912345678~TC=VISA~U4=1234|
     ^

   ← EVT_PUMP_STATUS_CHANGE_ID_001 → ST=AUTHORIZED, SU=MONEY_PRESET

2. CLIENTE DESPACHA:
   EVT_PUMP_STATUS_CHANGE_ID_001 → ST=FUELLING
   (EVT_PUMP_DELIVERY_PROGRESS opcionales)

3. FIN:
   EVT_PUMP_STATUS_CHANGE_ID_001 → ST=IDLE
   EVT_PUMP_NEW_TRANSACTION → SA=186, AM=50.00, PR=50.00, PAY_TY=TARJETA

   // VUELTO = PR - AM (si dispensó menos del preset)

4. HANDSHAKE (idéntico al caso 1)
```

### Caso 3: Cambio de surtidor en un preset activo

```
1. Cancelar preset actual:
   POST|REQ_PUMP_CLEAR_PRESET_ID_001||||^
   ← EVT_PUMP_STATUS_CHANGE_ID_001 → ST=IDLE

2. Enviar preset al nuevo surtidor:
   POST|REQ_PUMP_PRESET_ID_002|||VA=50.00|HO=1|TY=MONEY|^
```

---

## Flujo de cierre de turno

```
1. DETENER NUEVAS VENTAS:
   POST|REQ_PUMP_STOP_ID_000||||^

2. PAGAR VENTAS IMPAGAS (por cada una):
   POST|REQ_PAYMENT_CLEAR_SALE|||SA=xxx|TY=CIERRE_TURNO|^

3. CERRAR PERÍODO:
   POST|REQ_SHIFT_CLOSE_PERIOD|Shifts Add In||PT=S|^
   ← RES_SHIFT_CLOSE_PERIOD → ST=OK, PID=45

4. SOLICITAR REPORTES (con el PID obtenido):
   POST|REQ_SHIFT_PERIOD_SALES_BY_GRADE|Shifts Add In||PT=S|PID=45|^
   POST|REQ_SHIFT_PERIOD_SALES_BY_TYPE|Shifts Add In||PT=S|PID=45|^
   POST|REQ_SHIFT_PERIOD_SALES_BY_PAYMENT_TYPE|Shifts Add In||PT=S|PID=45|^
   POST|REQ_SHIFT_PERIOD_SALES_BY_HOSE_TYPE|Shifts Add In||PT=S|PID=45|^

5. LIBERAR SURTIDORES:
   POST|REQ_PUMP_CLEAR_STOP_ID_000||||^
```

---

## Implementación del FusionTcpClient en Quarkus

```java
@ApplicationScoped
public class FusionTcpClient {

    @Inject Vertx vertx;
    @Inject LeaderElection leaderElection;
    @Inject SseEventBus sseEventBus;
    @Inject OrdenDespachoRepository ordenRepo;

    private NetSocket socket;
    private final String fusionIp = "192.168.1.20";
    private final int fusionPort = 3011;
    private StringBuilder buffer = new StringBuilder();

    // ── CONEXIÓN ────────────────────────────────────────────

    public void conectar() {
        vertx.createNetClient()
            .connect(fusionPort, fusionIp, result -> {
                if (result.succeeded()) {
                    socket = result.result();
                    Log.info("Conectado a Wayne Fusion " + fusionIp + ":" + fusionPort);
                    socket.handler(this::onDataReceived);
                    socket.closeHandler(v -> onDesconectado());
                    enviarSuscripciones();
                    iniciarEcho();
                } else {
                    Log.error("Error conectando a Fusion: " + result.cause());
                    reconectarConBackoff();
                }
            });
    }

    public void desconectar() {
        if (socket != null) {
            socket.close();
            socket = null;
        }
    }

    // ── KEEP-ALIVE ECHO ─────────────────────────────────────

    @Scheduled(every = "120s")
    void enviarEcho() {
        if (!leaderElection.soyLider() || socket == null) return;
        // NOTA: ECHO usa su propio msg_type, no POST
        String echo = "00012|5|2||ECHO||||^";
        socket.write(Buffer.buffer(echo));
    }

    // ── SUSCRIPCIONES ───────────────────────────────────────

    private void enviarSuscripciones() {
        String[] suscripciones = {
            "EVT_PUMP_STATUS_CHANGE_ID_000",
            "EVT_PUMP_NEW_TRANSACTION",
            "EVT_NEW_CONFIG_APPLIED",
            "EVT_PAYMENT_SALE_CLEARED",
            "EVT_PAYMENT_ATTRIBUTES_CHANGE",
            "EVT_PAYMENT_TRANSACTION_LOCK",
            "EVT_NEW_PRICE_CHANGE_APPLIED",
            "EVT_PUMP_DELIVERY_PROGRESS_ID_000"  // opcional
        };

        for (String evento : suscripciones) {
            String body = "2||SUBSCRIBE|" + evento + "||||^";
            String msg = String.format("%05d|5|%s", body.length(), body);
            socket.write(Buffer.buffer(msg));
        }
    }

    // ── ENVÍO DE MENSAJES ───────────────────────────────────

    public void enviarMensaje(String eventType, String params) {
        if (socket == null) throw new IllegalStateException("Sin conexión a Fusion");
        String body = "2||POST|" + eventType + "|||" + params + "|^";
        String msg = String.format("%05d|5|%s", body.length(), body);
        socket.write(Buffer.buffer(msg));
        Log.debug("→ Fusion: " + msg);
    }

    // ── RECEPCIÓN DE MENSAJES ───────────────────────────────

    private void onDataReceived(Buffer data) {
        buffer.append(data.toString());
        procesarBuffer();
    }

    private void procesarBuffer() {
        String contenido = buffer.toString();
        int pos;
        while ((pos = contenido.indexOf('^')) >= 0) {
            String mensaje = contenido.substring(0, pos + 1);
            procesarMensaje(mensaje);
            contenido = contenido.substring(pos + 1);
        }
        buffer = new StringBuilder(contenido);
    }

    private void procesarMensaje(String mensaje) {
        Log.debug("← Fusion: " + mensaje);
        FusionMessage parsed = FusionMessage.parse(mensaje);

        switch (parsed.eventType) {
            case "EVT_PUMP_STATUS_CHANGE_ID_001",
                 "EVT_PUMP_STATUS_CHANGE_ID_002" -> onPumpStatusChange(parsed);
            case "EVT_PUMP_NEW_TRANSACTION"       -> onNewTransaction(parsed);
            case "EVT_PUMP_DELIVERY_PROGRESS_ID_001",
                 "EVT_PUMP_DELIVERY_PROGRESS_ID_002" -> onDeliveryProgress(parsed);
            case "EVT_NEW_CONFIG_APPLIED"         -> onConfigChanged(parsed);
            case "EVT_NEW_PRICE_CHANGE_APPLIED"   -> onPriceChanged(parsed);
            case "ECHO"                           -> {} // ignorar
            default -> Log.debug("Evento no manejado: " + parsed.eventType);
        }
    }

    // ── HANDLERS DE EVENTOS ─────────────────────────────────

    private void onPumpStatusChange(FusionMessage msg) {
        int surtidor = extraerNumeroSurtidor(msg.eventType);
        String status = msg.params.get("ST");
        String subStatus = msg.params.get("SU");

        // Actualizar cache en memoria
        EstadoSurtidor estado = new EstadoSurtidor(surtidor, status, subStatus, msg.params);
        surtidoresCache.put(surtidor, estado);

        // Notificar a tablets via SSE
        sseEventBus.broadcast("SURTIDOR_" + surtidor, estado);
    }

    private void onNewTransaction(FusionMessage msg) {
        String saleId = msg.params.get("SA");
        String payIn = msg.params.get("PAY_IN");

        // Extraer ordenId del PAY_IN: "OV=OV-001~CLI=..."
        String ordenId = extraerCampoPayIn(payIn, "OV");

        if (ordenId != null) {
            OrdenDespacho orden = ordenRepo.findById(ordenId);
            if (orden != null) {
                orden.fusionSaleId = saleId;
                orden.volumenReal = new BigDecimal(msg.params.get("VO"));
                orden.montoReal = new BigDecimal(msg.params.get("AM"));
                orden.precioUnitario = new BigDecimal(msg.params.get("PU"));
                orden.estado = EstadoOrden.COMPLETADA;
                ordenRepo.save(orden);

                // Iniciar handshake de pago en otro hilo
                vertx.executeBlocking(() -> completarPago(orden, msg));
            }
        }

        // Notificar a tablets
        sseEventBus.broadcast("VENTA_COMPLETADA", msg.params);
    }

    private void completarPago(OrdenDespacho orden, FusionMessage msg) {
        String saleId = orden.fusionSaleId;
        String lockId = orden.id;

        // Lock
        enviarMensaje("REQ_PAYMENT_TRANSACTION_LOCK",
            "SA=" + saleId + "|LID=" + lockId + "|TMO=10");
        esperarRespuesta("RES_PAYMENT_TRANSACTION_LOCK");

        // Clear Sale
        enviarMensaje("REQ_PAYMENT_CLEAR_SALE",
            "SA=" + saleId + "|TY=" + orden.tipoPago + "|LID=" + lockId);
        esperarRespuesta("RES_PAYMENT_CLEAR_SALE");

        // Unlock
        enviarMensaje("REQ_PAYMENT_TRANSACTION_UNLOCK",
            "SA=" + saleId + "|LID=" + lockId);

        // Notificar a PowerFin
        orden.estado = EstadoOrden.PAGADA;
        ordenRepo.save(orden);
        powerFinClient.notificarVentaCompletada(orden);
    }

    // ── RECONEXIÓN ──────────────────────────────────────────

    private void onDesconectado() {
        Log.warn("Conexión con Fusion perdida");
        if (leaderElection.soyLider()) {
            reconectarConBackoff();
        }
    }

    private void reconectarConBackoff() {
        // Reintentos: 5s, 10s, 20s, 40s, 60s (máximo)
        long delay = Math.min(60000, (long) Math.pow(2, intentos) * 5000);
        vertx.setTimer(delay, id -> {
            if (leaderElection.soyLider()) {
                conectar();
            }
        });
    }
}
```

---

## Parser del protocolo Fusion

```java
public class FusionMessage {
    public String len;
    public String crypt;
    public String version;
    public String userId;
    public String msgType;
    public String eventType;
    public String destination;
    public String origin;
    public Map<String, String> params = new LinkedHashMap<>();
    public String raw;

    public static FusionMessage parse(String raw) {
        FusionMessage msg = new FusionMessage();
        msg.raw = raw.trim();

        // Quitar el ^ final
        String content = msg.raw.endsWith("^")
            ? msg.raw.substring(0, msg.raw.length() - 1)
            : msg.raw;

        String[] parts = content.split("\\|", -1);

        if (parts.length < 8) return msg;

        msg.len         = parts[0];
        msg.crypt       = parts[1];
        msg.version     = parts[2];
        msg.userId      = parts[3];
        msg.msgType     = parts[4];
        msg.eventType   = parts[5];
        msg.destination = parts[6];
        msg.origin      = parts[7];

        // Parsear parámetros: CAMPO=VALOR
        for (int i = 8; i < parts.length; i++) {
            if (parts[i].isEmpty()) continue;
            int eq = parts[i].indexOf('=');
            if (eq > 0) {
                String key = parts[i].substring(0, eq);
                String val = parts[i].substring(eq + 1);
                msg.params.put(key, val);
            }
        }

        return msg;
    }

    // Extraer número de surtidor del event name
    // "EVT_PUMP_STATUS_CHANGE_ID_001" → 1
    public int getPumpNumber() {
        String[] parts = eventType.split("_");
        try {
            return Integer.parseInt(parts[parts.length - 1]);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    // Extraer campo específico del PAY_IN
    // "OV=OV-001~CLI=0912345678~LISTA=VIP" campo="CLI" → "0912345678"
    public String getPayInField(String campo) {
        String payIn = params.getOrDefault("PAY_IN", "");
        for (String part : payIn.split("~")) {
            int eq = part.indexOf('=');
            if (eq > 0 && part.substring(0, eq).equals(campo)) {
                return part.substring(eq + 1);
            }
        }
        return null;
    }
}
```

---

## Pruebas de conectividad (Python — para debugging)

```python
import socket
import time

FUSION_IP   = "192.168.1.20"
FUSION_PORT = 3011

def build_msg(event_type, params="", destination="", origin=""):
    """Construye mensaje con len calculado correctamente."""
    body = f"2||POST|{event_type}|{destination}|{origin}|{params}|^"
    return f"{len(body):05d}|5|{body}"

def test_echo():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((FUSION_IP, FUSION_PORT))

    # ECHO — keep-alive
    echo = "00012|5|2||ECHO||||^"
    sock.sendall(echo.encode('ascii'))
    time.sleep(1)
    resp = sock.recv(1024).decode('ascii')
    print(f"ECHO: {resp}")
    assert "ECHO" in resp, "Fusion no respondió al ECHO"

    # Estado de surtidores
    msg = build_msg("REQ_PUMP_STATUS_ID_000")
    sock.sendall(msg.encode('ascii'))
    time.sleep(2)
    resp = sock.recv(4096).decode('ascii')
    print(f"Status: {resp}")

    sock.close()
```

---

## Respuestas de pruebas reales (GASOLINERA)

```
// ECHO
→ 00012|5|2||ECHO||||^
← 00031|5|2||ECHO||192.168.1.100:55790||^

// Version
→ 00035|5|2||POST|REQ_GET_FUSION_VERSION||||^
← 00187|5|2||POST|RES_GET_FUSION_VERSION|...|OS=Windows|MAC=68:1d:ef:31:53:86|HWV=V2|BIN=Rel-5.19.1|^

// Config general
→ 00037|5|2||POST|REQ_FCRT_GET_GRAL_CONFIG||||^
← 00263|5|2||POST|RES_FCRT_GET_GRAL_CONFIG|...|SNR=3|SNA=NEOPAUTE|CNY=EC|MUD=DOLLARS|DF=dd/mm/yyyy|DCV=3|DCP=3|DCM=2|^

// Config surtidores
→ 00053|5|2||POST|REQ_FCRT_PUMPS_CONFIG|||PC=POWERFIN|MID=001|^
← 00429|5|2||POST|RES_FCRT_PUMPS_CONFIG|...|PUMPS=1|P001HOSES=2|P001H1GRADE=1|P001H1PRICE=9.99900|P001LOOPID=Serial_COM1_loop|ATO=0|^

// Config grades
→ 00035|5|2||POST|REQ_FCRT_GRADES_CONFIG||||^
← 00293|5|2||POST|RES_FCRT_GRADES_CONFIG|...|GRADES=1|G001DES=SUPER|G001GNR=1|G001L01=9.999|^

// Config tanques
→ 00033|5|2||POST|REQ_FCRT_TANK_CONFIG||||^
← 00270|5|2||POST|RES_FCRT_TANK_CONFIG|...|TQT=1|T1TAG=TANQUE DE SUPER|T1CTY=20000|T1PID=1|^

// Abrir surtidor (CLOSED → ERROR sin HW físico)
→ 00033|5|2||POST|REQ_PUMP_OPEN_ID_001||||^
← 00094|5|2|GUEST|POST|EVT_PUMP_STATUS_CHANGE_ID_001||...|SU=|ST=ERROR|PR=0.00|HN=2|^

// Estado surtidor con HW conectado (esperado)
← EVT_PUMP_STATUS_CHANGE_ID_001|...|ST=IDLE|SU=|HN=2|^
```
