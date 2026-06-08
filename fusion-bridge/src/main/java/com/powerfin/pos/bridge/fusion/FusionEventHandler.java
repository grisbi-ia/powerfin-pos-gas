package com.powerfin.pos.bridge.fusion;

import com.powerfin.pos.bridge.dispenser.DispenserStatusCache;
import com.powerfin.pos.bridge.sse.StationEventBus;

import io.quarkus.logging.Log;
import jakarta.enterprise.context.ApplicationScoped;

import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;

@ApplicationScoped
public class FusionEventHandler {

    private final DispenserStatusCache statusCache;
    private final StationEventBus eventBus;
    private final String powerfinUrl;
    private final HttpClient httpClient;

    public FusionEventHandler(DispenserStatusCache statusCache, StationEventBus eventBus,
                              @ConfigProperty(name = "powerfin.url") String powerfinUrl) {
        this.statusCache = statusCache;
        this.eventBus = eventBus;
        this.powerfinUrl = powerfinUrl;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    public void handle(FusionMessage msg) {
        if (msg == null || msg.eventType == null) return;

        Log.debug(String.format("Handling event: %s", msg.eventType));

        if (msg.eventType.startsWith("EVT_PUMP_STATUS_CHANGE_ID_")) {
            handleStatusChange(msg);
        } else if (msg.eventType.startsWith("EVT_PUMP_DELIVERY_PROGRESS_ID_")) {
            handleDeliveryProgress(msg);
        } else {
            switch (msg.eventType) {
                case "EVT_PUMP_NEW_TRANSACTION":
                    handleNewTransaction(msg);
                    break;
                case "EVT_PAYMENT_TRANSACTION_LOCK":
                    handleTransactionLock(msg);
                    break;
                case "EVT_PAYMENT_SALE_CLEARED":
                    handleSaleCleared(msg);
                    break;
                case "EVT_NEW_PRICE_CHANGE_APPLIED":
                    handlePriceChange(msg);
                    break;
                case "EVT_NEW_CONFIG_APPLIED":
                    handleConfigChange(msg);
                    break;
                default:
                    Log.debug(String.format("Unhandled event: %s", msg.eventType));
            }
        }
    }

    private void handleStatusChange(FusionMessage msg) {
        int pumpNumber = msg.getPumpNumber();
        String status = msg.params.getOrDefault("ST", "UNKNOWN");
        String subStatus = msg.params.getOrDefault("SU", "");
        String hoseCount = msg.params.getOrDefault("HN", "0");
        String presetAmount = msg.params.getOrDefault("PR", "0.00");
        String grade = msg.params.getOrDefault("GR", "");
        String activeHoseStr = msg.params.getOrDefault("HO", "");
        // For AUTHORIZED state with PRESET, the hose is in PR_HO, not HO
        if (activeHoseStr.isEmpty()) {
            activeHoseStr = msg.params.getOrDefault("PR_HO", "");
        }
        // HO may be "3@1.150" — extract just the hose number
        int activeHose = 0;
        if (!activeHoseStr.isEmpty()) {
            String[] parts = activeHoseStr.split("@");
            activeHose = parseInt(parts[0], 0);
        }

        DispenserStatusCache.DispenserStatus dispenser = new DispenserStatusCache.DispenserStatus();
        dispenser.setDispenserId(pumpNumber);
        dispenser.setStatus(status);
        dispenser.setSubStatus(subStatus);
        dispenser.setHoseCount(parseInt(hoseCount, 0));
        dispenser.setPresetAmount(parseDouble(presetAmount, 0.0));
        dispenser.setGrade(grade);
        dispenser.setActiveHose(activeHose);
        dispenser.setConnected(true);

        statusCache.update(dispenser);

        eventBus.broadcast("PUMP_STATUS_CHANGE", java.util.Map.of(
            "dispenserId", pumpNumber,
            "status", status,
            "subStatus", subStatus,
            "presetAmount", parseDouble(presetAmount, 0.0),
            "activeHose", activeHose
        ));

        Log.info(String.format("Dispenser %d status: %s (sub: %s, hose: %d)",
            pumpNumber, status, subStatus, activeHose));
    }

    private void handleNewTransaction(FusionMessage msg) {
        String saleId = msg.params.getOrDefault("SA", "");
        String pumpNumber = msg.params.getOrDefault("PM", "0");
        String hose = msg.params.getOrDefault("HO", "0");
        String volume = msg.params.getOrDefault("VO", "0");
        String amount = msg.params.getOrDefault("AM", "0");
        String unitPrice = msg.params.getOrDefault("PU", "0");
        String payIn = msg.params.getOrDefault("PAY_IN", "");
        String orderId = FusionMessage.extractPayInField(payIn, "OV");

        int pumpId = parseInt(pumpNumber, 0);
        int hoseId = parseInt(hose, 0);

        eventBus.broadcast("NEW_TRANSACTION", java.util.Map.of(
            "saleId", saleId,
            "pumpNumber", pumpId,
            "hoseId", hoseId,
            "volume", volume,
            "amount", amount,
            "unitPrice", unitPrice,
            "payIn", payIn,
            "orderId", orderId != null ? orderId : ""
        ));

        Log.info(String.format("New transaction — saleId=%s, pump=%d, hose=%d, volume=%s, amount=%s, orderId=%s",
            saleId, pumpId, hoseId, volume, amount, orderId));

        // ── Complete dispatch on backend (POS-independent) ──────────
        // The POS may be offline (phone off, battery dead, no signal).
        // FusionBridge completes the dispatch directly so the sale is
        // never lost. The POS-side completeDispatch in +page.svelte
        // serves as a double-safe (idempotent).
        if (orderId != null && !orderId.isEmpty()) {
            completeDispatchOnBackend(orderId, saleId, volume, amount, unitPrice);
        }
    }

    /**
     * Call POST /api/pos/dispatches/{orderId}/complete on the POS Backend.
     * Retries up to 3 times with 1s backoff. Fire-and-forget (runs async,
     * failures are logged but never block the Fusion event loop).
     */
    private void completeDispatchOnBackend(String orderId, String saleId,
                                            String volume, String amount, String unitPrice) {
        String url = powerfinUrl + "/api/pos/dispatches/" + orderId + "/complete";
        String now = Instant.now().toString();
        String body = String.format(
            "{\"order_id\":\"%s\",\"fusion_sale_id\":\"%s\",\"volume\":\"%s\"," +
            "\"amount\":\"%s\",\"unit_price\":\"%s\",\"payment_method\":\"EFECTIVO\"," +
            "\"completed_at\":\"%s\"}",
            orderId, saleId, volume, amount, unitPrice, now);

        // Run on virtual thread so retries don't block the event loop
        Thread.startVirtualThread(() -> {
            for (int attempt = 1; attempt <= 3; attempt++) {
                try {
                    HttpRequest request = HttpRequest.newBuilder()
                            .uri(URI.create(url))
                            .timeout(Duration.ofSeconds(10))
                            .header("Content-Type", "application/json")
                            .POST(HttpRequest.BodyPublishers.ofString(body))
                            .build();

                    HttpResponse<String> response = httpClient.send(request,
                            HttpResponse.BodyHandlers.ofString());

                    if (response.statusCode() >= 200 && response.statusCode() < 300) {
                        Log.infof("completeDispatch OK: %s (attempt %d)", orderId, attempt);
                        return;
                    }
                    Log.warnf("completeDispatch %s returned %d (attempt %d)",
                            orderId, response.statusCode(), attempt);
                } catch (Exception e) {
                    Log.warnf("completeDispatch %s failed (attempt %d): %s",
                            orderId, attempt, e.getMessage());
                }

                if (attempt < 3) {
                    try { Thread.sleep(1000); } catch (InterruptedException ie) { break; }
                }
            }
            Log.errorf("completeDispatch %s FAILED after 3 attempts — sale may need manual reconciliation",
                    orderId);
        });
    }

    private void handleDeliveryProgress(FusionMessage msg) {
        int pumpNumber = msg.getPumpNumber();
        String volume = msg.params.getOrDefault("VO", "0");
        String amount = msg.params.getOrDefault("AM", "0");

        eventBus.broadcast("DELIVERY_PROGRESS", java.util.Map.of(
            "dispenserId", pumpNumber,
            "volume", volume,
            "amount", amount
        ));
    }

    private void handleTransactionLock(FusionMessage msg) {
        String saleId = msg.params.getOrDefault("SA", "");
        String lockId = msg.params.getOrDefault("LID", "");

        eventBus.broadcast("TRANSACTION_LOCK", java.util.Map.of(
            "saleId", saleId,
            "lockId", lockId
        ));
    }

    private void handleSaleCleared(FusionMessage msg) {
        String saleId = msg.params.getOrDefault("SA", "");
        eventBus.broadcast("SALE_CLEARED", java.util.Map.of(
            "saleId", saleId
        ));
    }

    private void handlePriceChange(FusionMessage msg) {
        String result = msg.params.getOrDefault("RC", "ERROR");
        eventBus.broadcast("PRICE_CHANGE", java.util.Map.of(
            "result", result
        ));
    }

    private void handleConfigChange(FusionMessage msg) {
        eventBus.broadcast("CONFIG_CHANGE", java.util.Map.of());
    }

    private int parseInt(String value, int defaultVal) {
        try { return Integer.parseInt(value); } catch (NumberFormatException e) { return defaultVal; }
    }

    private double parseDouble(String value, double defaultVal) {
        try { return Double.parseDouble(value); } catch (NumberFormatException e) { return defaultVal; }
    }
}
