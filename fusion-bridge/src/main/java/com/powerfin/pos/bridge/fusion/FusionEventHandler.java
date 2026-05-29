package com.powerfin.pos.bridge.fusion;

import com.powerfin.pos.bridge.dispenser.DispenserStatusCache;
import com.powerfin.pos.bridge.sse.StationEventBus;

import io.quarkus.logging.Log;
import jakarta.enterprise.context.ApplicationScoped;

@ApplicationScoped
public class FusionEventHandler {

    private final DispenserStatusCache statusCache;
    private final StationEventBus eventBus;

    public FusionEventHandler(DispenserStatusCache statusCache, StationEventBus eventBus) {
        this.statusCache = statusCache;
        this.eventBus = eventBus;
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
        String volume = msg.params.getOrDefault("VO", "0");
        String amount = msg.params.getOrDefault("AM", "0");
        String unitPrice = msg.params.getOrDefault("PU", "0");
        String payIn = msg.params.getOrDefault("PAY_IN", "");

        eventBus.broadcast("NEW_TRANSACTION", java.util.Map.of(
            "saleId", saleId,
            "pumpNumber", parseInt(pumpNumber, 0),
            "volume", volume,
            "amount", amount,
            "unitPrice", unitPrice,
            "payIn", payIn
        ));

        Log.info(String.format("New transaction — saleId=%s, pump=%s, volume=%s, amount=%s",
            saleId, pumpNumber, volume, amount));
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
