# FusionBridge — Documentación Técnica

## ¿Qué es FusionBridge?

Microservicio liviano cuya única responsabilidad es ser el intermediario
entre el ecosistema de software (PowerFin + Powerfin POS) y el hardware
Wayne Fusion/Synergy. También gestiona la impresión de tickets en las
impresoras térmicas de red de cada isla.

```
NO tiene base de datos propia.
NO tiene pantalla ni interfaz de usuario.
NO conoce de clientes, precios ni contabilidad.
SÍ habla TCP con el Fusion, REST/SSE con el resto, y ESC/POS con las impresoras.
```

---

## Stack tecnológico

```
Framework:   Quarkus 3.x
Lenguaje:    Java 21 (Virtual Threads — Project Loom)
TCP Client:  Vert.x NetClient (incluido en Quarkus)
REST Server: Quarkus REST (RESTEasy Reactive)
SSE:         Quarkus SSE nativo
Scheduler:   Quarkus Scheduler (ECHO keep-alive)
Deploy:      Servicio systemd en Debian 12
```

---

## Responsabilidades

```
Comunicación con hardware Fusion/Synergy:
  1. Mantener conexión TCP persistente (192.168.1.20:3011)
  2. Enviar ECHO cada 120 segundos
  3. Reconectar automáticamente con backoff exponencial
  4. Suscribirse a eventos del Fusion al conectar
  5. Recibir y procesar eventos (status, transacciones, progreso)

Comunicación hacia el sistema:
  6. Exponer estado de surtidores via REST
  7. Emitir eventos via SSE hacia el Powerfin POS en tiempo real
  8. Recibir órdenes de autorización via REST
  9. Hacer el handshake de pago (Lock → ClearSale → Unlock)
  10. Notificar a PowerFin cuando un despacho termina

Impresión:
  11. Recibir solicitudes de impresión desde el Powerfin POS
  12. Generar bytes ESC/POS del ticket
  13. Enviar por socket TCP directo a la impresora de la isla

Resiliencia:
  14. Guardar ventas en cola local si PowerFin no responde
  15. Reintentar el envío cada 30 segundos
```

---

## Estructura del proyecto

```
fusion-bridge/
├── src/main/java/com/powerfin/pos/bridge/
│   ├── fusion/
│   │   ├── FusionTcpClient.java        ← conexión TCP persistente
│   │   ├── FusionMessage.java          ← parser de mensajes
│   │   ├── FusionMessageBuilder.java   ← constructor de mensajes
│   │   └── FusionEventHandler.java     ← procesa eventos entrantes
│   ├── dispenser/
│   │   ├── DispenserStatusCache.java   ← estado en memoria
│   │   └── DispenserResource.java      ← GET /api/dispensers
│   ├── dispatch/
│   │   ├── DispatchResource.java       ← POST /api/dispatch/authorize
│   │   ├── DispatchService.java        ← handshake + notificación PowerFin
│   │   └── PendingSalesQueue.java      ← cola local de emergencia
│   ├── print/
│   │   ├── PrintResource.java          ← POST /api/print
│   │   ├── ReceiptBuilder.java         ← genera bytes ESC/POS
│   │   ├── ThermalPrinter.java         ← socket TCP a la impresora
│   │   └── PrinterConfig.java          ← IPs y política de impresión
│   ├── sse/
│   │   └── StationEventBus.java        ← SSE broadcaster
│   ├── powerfin/
│   │   └── PowerFinClient.java         ← REST client hacia PowerFin
│   └── health/
│       └── BridgeHealthResource.java   ← GET /health
│
├── src/test/java/com/powerfin/pos/bridge/
│   ├── fusion/
│   │   ├── FusionMessageTest.java
│   │   └── FusionMessageBuilderTest.java
│   ├── dispatch/
│   │   └── DispatchServiceTest.java
│   └── print/
│       └── ReceiptBuilderTest.java
│
├── src/main/resources/
│   └── application.properties
├── pom.xml
└── Dockerfile                          ← solo para build, no para deploy
```

---

## Dependencias Maven (pom.xml)

```xml
<properties>
    <quarkus.version>3.8.0</quarkus.version>
    <java.version>21</java.version>
</properties>

<dependencies>
    <!-- REST server -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-rest</artifactId>
    </dependency>
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-rest-jackson</artifactId>
    </dependency>

    <!-- REST client hacia PowerFin -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-rest-client</artifactId>
    </dependency>

    <!-- TCP client (Vert.x incluido en Quarkus) -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-vertx</artifactId>
    </dependency>

    <!-- Scheduler para ECHO keep-alive y reintentos -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-scheduler</artifactId>
    </dependency>

    <!-- Health checks -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-smallrye-health</artifactId>
    </dependency>

    <!-- Virtual Threads -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-virtual-threads</artifactId>
    </dependency>

    <!-- ESC/POS para impresoras térmicas -->
    <dependency>
        <groupId>com.github.anastaciocintra</groupId>
        <artifactId>escpos-coffee</artifactId>
        <version>4.1.0</version>
    </dependency>
</dependencies>
```

---

## application.properties

```properties
# Servidor
quarkus.http.port=8090
quarkus.http.host=0.0.0.0

# CORS — permite Powerfin POS desde Nginx
quarkus.http.cors=true
quarkus.http.cors.origins=https://pos.gasolinera.com

# Wayne Fusion/Synergy
fusion.ip=${FUSION_IP:192.168.1.20}
fusion.port=${FUSION_PORT:3011}
fusion.echo.interval.seconds=120
fusion.reconnect.max.delay.seconds=60

# PowerFin ERP
powerfin.url=${POWERFIN_URL:http://localhost:8080}
powerfin.api.key=${POWERFIN_API_KEY}
powerfin.timeout.seconds=10

# Cola de emergencia
pending.sales.file=${PENDING_SALES_FILE:/var/lib/powerfin/pos/pending_sales.json}

# Impresión
# Política: ALWAYS | ASK | NEVER
printer.policy=${PRINTER_POLICY:ASK}

# Impresora Isla 1
printer.island1.ip=${PRINTER_ISLAND1_IP:192.168.1.31}
printer.island1.port=${PRINTER_ISLAND1_PORT:9100}

# Impresora Isla 2 (si existe)
printer.island2.ip=${PRINTER_ISLAND2_IP:192.168.1.32}
printer.island2.port=${PRINTER_ISLAND2_PORT:9100}
```

---

## FusionTcpClient.java

```java
@ApplicationScoped
public class FusionTcpClient {

    @Inject Vertx               vertx;
    @Inject FusionEventHandler  eventHandler;
    @Inject StationEventBus     eventBus;

    @ConfigProperty(name = "fusion.ip")   String fusionIp;
    @ConfigProperty(name = "fusion.port") int    fusionPort;

    private NetSocket       socket;
    private final StringBuilder buffer = new StringBuilder();
    private int             reconnectAttempts = 0;
    private volatile boolean connected        = false;

    private static final String[] MANDATORY_SUBSCRIPTIONS = {
        "EVT_PUMP_STATUS_CHANGE_ID_000",
        "EVT_PUMP_NEW_TRANSACTION",
        "EVT_PAYMENT_SALE_CLEARED",
        "EVT_PAYMENT_TRANSACTION_LOCK",
        "EVT_NEW_PRICE_CHANGE_APPLIED",
        "EVT_PUMP_DELIVERY_PROGRESS_ID_000"
    };

    void onStart(@Observes StartupEvent ev) {
        connect();
    }

    public void connect() {
        Log.info("Connecting to Wayne Fusion {}:{}", fusionIp, fusionPort);
        vertx.createNetClient()
            .connect(fusionPort, fusionIp, result -> {
                if (result.succeeded()) {
                    socket            = result.result();
                    connected         = true;
                    reconnectAttempts = 0;
                    Log.info("Connected to Wayne Fusion OK");

                    socket.handler(this::onDataReceived);
                    socket.closeHandler(v -> onDisconnected());
                    socket.exceptionHandler(e -> {
                        Log.error("Socket error: {}", e.getMessage());
                        onDisconnected();
                    });

                    sendSubscriptions();
                    sendMessage("REQ_PUMP_STATUS_ID_000", "");

                } else {
                    Log.error("Failed to connect: {}", result.cause().getMessage());
                    connected = false;
                    reconnectWithBackoff();
                }
            });
    }

    @Scheduled(every = "120s")
    void sendEcho() {
        if (!connected || socket == null) return;
        socket.write(Buffer.buffer("00012|5|2||ECHO||||^"));
    }

    private void sendSubscriptions() {
        for (String event : MANDATORY_SUBSCRIPTIONS) {
            String body = "2||SUBSCRIBE|" + event + "||||^";
            socket.write(Buffer.buffer(String.format("%05d|5|%s", body.length(), body)));
        }
        Log.info("Subscriptions sent");
    }

    public boolean sendMessage(String eventType, String params) {
        if (!connected || socket == null) return false;
        String body = "2||POST|" + eventType + "|||" + params + "|^";
        String msg  = String.format("%05d|5|%s", body.length(), body);
        socket.write(Buffer.buffer(msg));
        Log.debug("→ Fusion: {}", msg);
        return true;
    }

    private void onDataReceived(Buffer data) {
        buffer.append(data.toString());
        String content = buffer.toString();
        int pos;
        while ((pos = content.indexOf('^')) >= 0) {
            String raw = content.substring(0, pos + 1).trim();
            if (!raw.isEmpty()) eventHandler.handle(FusionMessage.parse(raw));
            content = content.substring(pos + 1);
        }
        buffer.replace(0, buffer.length(), content);
    }

    private void onDisconnected() {
        connected = false;
        socket    = null;
        Log.warn("Fusion connection lost");
        eventBus.broadcast("FUSION_DISCONNECTED", Map.of("connected", false));
        reconnectWithBackoff();
    }

    private void reconnectWithBackoff() {
        long delayMs = Math.min(60_000L,
            (long) Math.pow(2, reconnectAttempts) * 5_000L);
        reconnectAttempts++;
        vertx.setTimer(delayMs, id -> connect());
    }

    public boolean isConnected() { return connected; }
}
```

---

## FusionMessage.java — Parser

```java
public class FusionMessage {

    public String              raw;
    public String              msgType;
    public String              eventType;
    public String              destination;
    public String              origin;
    public Map<String, String> params = new LinkedHashMap<>();

    public static FusionMessage parse(String raw) {
        FusionMessage msg = new FusionMessage();
        msg.raw = raw.trim();

        String content = msg.raw.endsWith("^")
            ? msg.raw.substring(0, msg.raw.length() - 1) : msg.raw;

        String[] parts = content.split("\\|", -1);
        if (parts.length < 6) return msg;

        // partes: len | crypt | version | user_id | msg_type | event | dest | origin | params...
        msg.msgType     = parts[4];
        msg.eventType   = parts[5];
        msg.destination = parts.length > 6 ? parts[6] : "";
        msg.origin      = parts.length > 7 ? parts[7] : "";

        for (int i = 8; i < parts.length; i++) {
            if (parts[i].isEmpty()) continue;
            int eq = parts[i].indexOf('=');
            if (eq > 0) msg.params.put(
                parts[i].substring(0, eq),
                parts[i].substring(eq + 1)
            );
        }
        return msg;
    }

    // "EVT_PUMP_STATUS_CHANGE_ID_001" → 1
    public int getPumpNumber() {
        if (eventType == null) return 0;
        try {
            String[] p = eventType.split("_");
            return Integer.parseInt(p[p.length - 1]);
        } catch (NumberFormatException e) { return 0; }
    }

    // Extrae campo del PAY_IN: "OV=OV-001~CLI=123" campo="OV" → "OV-001"
    public static String extractPayInField(String payIn, String field) {
        if (payIn == null || payIn.isEmpty()) return null;
        for (String part : payIn.split("~")) {
            int eq = part.indexOf('=');
            if (eq > 0 && part.substring(0, eq).equals(field))
                return part.substring(eq + 1);
        }
        return null;
    }
}
```

---

## FusionMessageBuilder.java

```java
public class FusionMessageBuilder {

    public static String build(String eventType, String params) {
        String body = "2||POST|" + eventType + "|||" + params + "|^";
        return String.format("%05d|5|%s", body.length(), body);
    }

    // Preset de despacho — el mensaje más importante
    public static String buildPreset(int pumpId, String presetType, String value,
                                     int hose, double unitPrice, String orderId,
                                     String customerId, String plate,
                                     String priceList, String paymentMethod) {
        String hoseWithPrice = hose + "@" + String.format("%.3f", unitPrice);
        String payIn = "OV=" + orderId
            + "~CLI=" + (customerId != null ? customerId : "FINAL")
            + "~PLC=" + (plate      != null ? plate      : "")
            + "~LISTA=" + priceList;

        String params = "TY=" + presetType
            + "|VA=" + value
            + "|HO=" + hoseWithPrice
            + "|PAY_TY=" + paymentMethod
            + "|PAY_IN=" + payIn
            + "|FTS=YES";

        return build("REQ_PUMP_PRESET_ID_" + String.format("%03d", pumpId), params);
    }

    public static String buildLock(String saleId, String lockId) {
        return build("REQ_PAYMENT_TRANSACTION_LOCK",
            "SA=" + saleId + "|LID=" + lockId + "|TMO=10");
    }

    public static String buildClearSale(String saleId, String lockId, String method) {
        return build("REQ_PAYMENT_CLEAR_SALE",
            "SA=" + saleId + "|TY=" + method + "|LID=" + lockId);
    }

    public static String buildUnlock(String saleId, String lockId) {
        return build("REQ_PAYMENT_TRANSACTION_UNLOCK",
            "SA=" + saleId + "|LID=" + lockId);
    }

    public static String buildStopAll()      { return build("REQ_PUMP_STOP_ID_000", "PA=1"); }
    public static String buildClearStopAll() { return build("REQ_PUMP_CLEAR_STOP_ID_000", ""); }
}
```

---

## DispatchService.java

```java
@ApplicationScoped
public class DispatchService {

    @Inject FusionTcpClient  fusionClient;
    @Inject PowerFinClient   powerFinClient;
    @Inject StationEventBus  eventBus;
    @Inject PendingSalesQueue pendingQueue;

    // Llamado cuando llega EVT_PUMP_NEW_TRANSACTION
    @RunOnVirtualThread
    public void completePayment(String saleId, String orderId,
                                Map<String, String> params) {
        try {
            String volume        = params.getOrDefault("VO", "0");
            String amount        = params.getOrDefault("AM", "0");
            String unitPrice     = params.getOrDefault("PU", "0");
            String paymentMethod = params.getOrDefault("PAY_TY", "CASH");

            // Handshake con Fusion
            fusionClient.sendMessage("REQ_PAYMENT_TRANSACTION_LOCK",
                "SA=" + saleId + "|LID=" + orderId + "|TMO=10");
            Thread.sleep(500);

            fusionClient.sendMessage("REQ_PAYMENT_CLEAR_SALE",
                "SA=" + saleId + "|TY=" + paymentMethod + "|LID=" + orderId);
            Thread.sleep(500);

            fusionClient.sendMessage("REQ_PAYMENT_TRANSACTION_UNLOCK",
                "SA=" + saleId + "|LID=" + orderId);

            // Notificar a PowerFin
            SaleCompletedDto sale = new SaleCompletedDto(
                orderId, saleId,
                new BigDecimal(volume),
                new BigDecimal(amount),
                new BigDecimal(unitPrice),
                paymentMethod,
                LocalDateTime.now()
            );
            notifyPowerFin(sale);

            // Notificar al Powerfin POS via SSE
            eventBus.broadcast("SALE_COMPLETED", Map.of(
                "orderId", orderId,
                "volume",  volume,
                "amount",  amount
            ));

            Log.info("Payment completed — orderId={}, amount={}", orderId, amount);

        } catch (Exception e) {
            Log.error("Error completing payment saleId={}: {}", saleId, e.getMessage());
        }
    }

    private void notifyPowerFin(SaleCompletedDto sale) {
        try {
            powerFinClient.notifySaleCompleted(sale);
        } catch (Exception e) {
            Log.warn("PowerFin unavailable — queuing sale {}", sale.orderId);
            pendingQueue.add(sale);
        }
    }
}
```

---

## Módulo de impresión

### PrinterConfig.java

```java
@ApplicationScoped
public class PrinterConfig {

    public enum Policy { ALWAYS, ASK, NEVER }

    @ConfigProperty(name = "printer.policy")
    String policyStr;

    @ConfigProperty(name = "printer.island1.ip")   String island1Ip;
    @ConfigProperty(name = "printer.island1.port")  int    island1Port;
    @ConfigProperty(name = "printer.island2.ip")   String island2Ip;
    @ConfigProperty(name = "printer.island2.port")  int    island2Port;

    public Policy getPolicy() {
        return Policy.valueOf(policyStr.toUpperCase());
    }

    // Retorna la IP de la impresora según el número de isla del surtidor
    public String getPrinterIp(int dispenserId) {
        // Surtidores 1-2 → Isla 1, Surtidores 3-4 → Isla 2
        // Ajustar según configuración real de GASOLINERA
        return dispenserId <= 2 ? island1Ip : island2Ip;
    }

    public int getPrinterPort(int dispenserId) {
        return dispenserId <= 2 ? island1Port : island2Port;
    }
}
```

### ReceiptBuilder.java

```java
@ApplicationScoped
public class ReceiptBuilder {

    // Genera los bytes ESC/POS del ticket de despacho
    public byte[] buildFuelReceipt(FuelReceiptData data) throws IOException {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        EscPos escPos = new EscPos(baos);

        Style titleStyle = new Style()
            .setFontSize(Style.FontSize._2, Style.FontSize._2)
            .setJustification(EscPosConst.Justification.Center)
            .setBold(true);

        Style normalStyle = new Style()
            .setJustification(EscPosConst.Justification.Left);

        Style rightStyle = new Style()
            .setJustification(EscPosConst.Justification.Right);

        // Encabezado
        escPos.writeLF(titleStyle, data.locationName);
        escPos.writeLF(new Style().setJustification(EscPosConst.Justification.Center),
            data.locationAddress);
        escPos.writeLF(new Style().setJustification(EscPosConst.Justification.Center),
            "RUC: " + data.locationRuc);
        escPos.write(normalStyle, "--------------------------------\n");

        // Datos del despacho
        escPos.writeLF(normalStyle, "Fecha: " + data.date + "  " + data.time);
        escPos.writeLF(normalStyle, "Surtidor: " + data.dispenserId +
            "  Pistola: " + data.hoseId);
        escPos.write(normalStyle, "--------------------------------\n");
        escPos.writeLF(new Style().setBold(true), data.grade);
        escPos.writeLF(normalStyle,
            String.format("%-20s %10s", "Volumen (litros):", data.volume));
        escPos.writeLF(normalStyle,
            String.format("%-20s %10s", "Precio unitario:", "$" + data.unitPrice));

        escPos.write(normalStyle, "================================\n");
        escPos.writeLF(titleStyle, "TOTAL:  $" + data.amount);
        escPos.write(normalStyle, "================================\n");

        // Forma de pago
        escPos.writeLF(normalStyle, "Pago: " + data.paymentMethod);

        // Cliente (si está identificado)
        if (data.customerName != null && !data.customerName.isEmpty()) {
            escPos.writeLF(normalStyle, "Cliente: " + data.customerName);
        }
        if (data.plate != null && !data.plate.isEmpty()) {
            escPos.writeLF(normalStyle, "Placa: " + data.plate);
        }

        // Factura
        escPos.write(normalStyle, "--------------------------------\n");
        if (data.invoiceId != null && !data.invoiceId.isEmpty()) {
            escPos.writeLF(normalStyle, "Factura: " + data.invoiceId);
            escPos.writeLF(new Style().setJustification(EscPosConst.Justification.Center),
                "Autorización SRI");
            escPos.writeLF(new Style()
                .setJustification(EscPosConst.Justification.Center)
                .setFontSize(Style.FontSize._1, Style.FontSize._1),
                data.invoiceAuth);
        } else {
            escPos.writeLF(new Style().setJustification(EscPosConst.Justification.Center),
                "Factura pendiente de emision");
        }

        // Pie
        escPos.write(normalStyle, "--------------------------------\n");
        escPos.writeLF(new Style().setJustification(EscPosConst.Justification.Center),
            "Gracias por su preferencia");

        // Corte
        escPos.cut(EscPos.CutMode.FULL);

        escPos.close();
        return baos.toByteArray();
    }
}
```

### ThermalPrinter.java

```java
@ApplicationScoped
public class ThermalPrinter {

    private static final int SOCKET_TIMEOUT_MS = 5_000;

    // Envío directo por socket TCP — sin drivers, sin CUPS
    public void print(String printerIp, int printerPort, byte[] data) {
        Log.info("Printing to {}:{} ({} bytes)", printerIp, printerPort, data.length);
        try (Socket socket = new Socket()) {
            socket.connect(
                new InetSocketAddress(printerIp, printerPort),
                SOCKET_TIMEOUT_MS
            );
            socket.setSoTimeout(SOCKET_TIMEOUT_MS);
            socket.getOutputStream().write(data);
            socket.getOutputStream().flush();
            Log.info("Print sent successfully to {}", printerIp);

        } catch (ConnectException e) {
            Log.error("Printer {}:{} not reachable: {}", printerIp, printerPort, e.getMessage());
            throw new PrintException("Printer not reachable: " + printerIp);
        } catch (IOException e) {
            Log.error("Print error: {}", e.getMessage());
            throw new PrintException("Print failed: " + e.getMessage());
        }
    }
}
```

### PrintResource.java

```java
@Path("/api/print")
@ApplicationScoped
public class PrintResource {

    @Inject ReceiptBuilder  receiptBuilder;
    @Inject ThermalPrinter  printer;
    @Inject PrinterConfig   printerConfig;

    @POST
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    @RunOnVirtualThread
    public Response print(PrintRequestDto request) {
        try {
            byte[] receipt;

            switch (request.type) {
                case "FUEL_RECEIPT" -> receipt = receiptBuilder
                    .buildFuelReceipt(request.fuelData);
                default -> {
                    return Response.status(400)
                        .entity(Map.of("error", "Unknown receipt type: " + request.type))
                        .build();
                }
            }

            String ip   = printerConfig.getPrinterIp(request.dispenserId);
            int    port = printerConfig.getPrinterPort(request.dispenserId);
            printer.print(ip, port, receipt);

            return Response.ok(Map.of(
                "status",     "PRINTED",
                "printerIp",  ip
            )).build();

        } catch (PrintException e) {
            return Response.status(503)
                .entity(Map.of("error", e.getMessage()))
                .build();
        } catch (Exception e) {
            Log.error("Print error: {}", e.getMessage());
            return Response.status(500)
                .entity(Map.of("error", "Internal error"))
                .build();
        }
    }

    // Endpoint para que el Powerfin POS consulte la política configurada
    @GET
    @Path("/policy")
    @Produces(MediaType.APPLICATION_JSON)
    public Response getPolicy() {
        return Response.ok(Map.of(
            "policy", printerConfig.getPolicy().name()
        )).build();
    }
}
```

---

## APIs que expone FusionBridge

```
GET  /api/dispensers              → estado de todos los surtidores
GET  /api/dispensers/{id}         → estado de un surtidor
GET  /api/events                  → SSE stream de eventos en tiempo real
POST /api/dispatch/authorize      → enviar preset al Fusion
POST /api/dispatch/cancel         → cancelar preset activo
GET  /api/print/policy            → política de impresión configurada
POST /api/print                   → imprimir ticket
GET  /health                      → health check completo
```

---

## GET /health — respuesta

```json
{
  "status": "UP",
  "fusionConnected": true,
  "fusionIp": "192.168.1.20",
  "powerFinReachable": true,
  "pendingSales": 0,
  "printerPolicy": "ASK",
  "printers": {
    "island1": { "ip": "192.168.1.31", "reachable": true },
    "island2": { "ip": "192.168.1.32", "reachable": true }
  }
}
```

---

## PendingSalesQueue.java

```java
@ApplicationScoped
public class PendingSalesQueue {

    @ConfigProperty(name = "pending.sales.file")
    String filePath;

    @Inject PowerFinClient powerFinClient;

    private final Queue<SaleCompletedDto> queue = new ConcurrentLinkedQueue<>();

    public void add(SaleCompletedDto sale) {
        queue.offer(sale);
        persistToFile();
        Log.warn("Sale {} queued. Total pending: {}", sale.orderId, queue.size());
    }

    @Scheduled(every = "30s")
    void retryPending() {
        if (queue.isEmpty()) return;
        List<SaleCompletedDto> toRetry = new ArrayList<>(queue);
        for (SaleCompletedDto sale : toRetry) {
            try {
                powerFinClient.notifySaleCompleted(sale);
                queue.remove(sale);
                Log.info("Pending sale {} sent to PowerFin", sale.orderId);
            } catch (Exception e) {
                Log.debug("PowerFin still unavailable for {}", sale.orderId);
            }
        }
        if (!queue.isEmpty()) persistToFile();
        else deleteFile();
    }

    void onStart(@Observes StartupEvent ev) { loadFromFile(); }

    private void persistToFile() { /* serializar queue a JSON */ }
    private void loadFromFile()  { /* deserializar desde JSON */ }
    private void deleteFile()    { /* limpiar archivo */ }
}
```
