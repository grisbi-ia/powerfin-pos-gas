package com.powerfin.pos.bridge.fusion;

import io.quarkus.logging.Log;
import io.quarkus.runtime.StartupEvent;
import io.quarkus.scheduler.Scheduled;
import io.vertx.core.Vertx;
import io.vertx.core.buffer.Buffer;
import io.vertx.core.net.NetSocket;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;

@ApplicationScoped
public class FusionTcpClient {

    @Inject
    Vertx vertx;

    @Inject
    FusionEventHandler eventHandler;

    @Inject
    com.powerfin.pos.bridge.sse.StationEventBus eventBus;

    @ConfigProperty(name = "fusion.ip")
    String fusionIp;

    @ConfigProperty(name = "fusion.port")
    int fusionPort;

    private NetSocket socket;
    private final StringBuilder buffer = new StringBuilder();
    private int reconnectAttempts = 0;
    private volatile boolean connected = false;

    private static final String[] MANDATORY_SUBSCRIPTIONS = {
        "EVT_PUMP_STATUS_CHANGE_ID_000",
        "EVT_PUMP_NEW_TRANSACTION",
        "EVT_PAYMENT_SALE_CLEARED",
        "EVT_PAYMENT_TRANSACTION_LOCK",
        "EVT_NEW_PRICE_CHANGE_APPLIED",
        "EVT_NEW_CONFIG_APPLIED"
    };

    void onStart(@Observes StartupEvent ev) {
        connect();
    }

    public void connect() {
        Log.info(String.format("Connecting to Wayne Fusion %s:%d", fusionIp, fusionPort));
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
                        Log.error("Socket error", e);
                        onDisconnected();
                    });

                    sendSubscriptions();
                    sendPumpStatusRequest();
                    eventBus.broadcastConnected(true);

                } else {
                    Log.error(String.format("Failed to connect: %s",
                        result.cause().getMessage()));
                    connected = false;
                    reconnectWithBackoff();
                }
            });
    }

    @Scheduled(every = "120s")
    void sendEcho() {
        if (!connected || socket == null) return;
        String echo = FusionMessageBuilder.buildEcho();
        socket.write(Buffer.buffer(echo));
        Log.debug("ECHO sent");
    }

    public boolean sendMessage(String eventType, String params) {
        return sendMessage(eventType, params, "", "");
    }

    public boolean sendMessage(String eventType, String params,
                                String destination, String origin) {
        if (!connected || socket == null) return false;
        String msg = FusionMessageBuilder.build(eventType, params, destination, origin);
        socket.write(Buffer.buffer(msg));
        Log.debug(String.format("→ Fusion: %s", msg));
        return true;
    }

    /** Send a pre-built raw Fusion protocol message directly. */
    public boolean sendRaw(String rawMessage) {
        if (!connected || socket == null) return false;
        socket.write(Buffer.buffer(rawMessage));
        Log.debug(String.format("→ Fusion: %s", rawMessage));
        return true;
    }

    private void sendSubscriptions() {
        for (String event : MANDATORY_SUBSCRIPTIONS) {
            String msg = FusionMessageBuilder.buildSubscribe(event);
            socket.write(Buffer.buffer(msg));
        }
        Log.info(String.format("Subscriptions sent (%d)", MANDATORY_SUBSCRIPTIONS.length));
    }

    private void sendPumpStatusRequest() {
        sendMessage("REQ_PUMP_STATUS_ID_000", "");
    }

    private void onDataReceived(Buffer data) {
        buffer.append(data.toString());
        String content = buffer.toString();
        int pos;
        while ((pos = content.indexOf('^')) >= 0) {
            String raw = content.substring(0, pos + 1).trim();
            if (!raw.isEmpty()) {
                try {
                    FusionMessage msg = FusionMessage.parse(raw);
                    if (msg.eventType != null && !msg.eventType.isEmpty()) {
                        eventHandler.handle(msg);
                    }
                } catch (Exception e) {
                    Log.error("Error parsing message", e);
                }
            }
            content = content.substring(pos + 1);
        }
        buffer.replace(0, buffer.length(), content);
    }

    private void onDisconnected() {
        connected = false;
        socket    = null;
        Log.warn("Fusion connection lost");
        eventBus.broadcastConnected(false);
        reconnectWithBackoff();
    }

    private void reconnectWithBackoff() {
        long delayMs = Math.min(60_000L,
            (long) Math.pow(2, reconnectAttempts) * 5_000L);
        reconnectAttempts++;
        Log.info(String.format("Reconnecting in %dms (attempt %d)",
            delayMs, reconnectAttempts));
        vertx.setTimer(delayMs, id -> connect());
    }

    public boolean isConnected() {
        return connected;
    }

    public String getFusionIp() {
        return fusionIp;
    }
}
