package com.powerfin.pos.bridge.fusion;

public class FusionMessageBuilder {

    public static String build(String eventType, String params) {
        return build(eventType, params, "", "");
    }

    public static String build(String eventType, String params,
                               String destination, String origin) {
        String body = "2||POST|" + eventType + "|" + destination
            + "|" + origin + "|" + params + "|^";
        return String.format("%05d|5|%s", body.length(), body);
    }

    public static String buildEcho() {
        return "00012|5|2||ECHO||||^";
    }

    public static String buildSubscribe(String eventType) {
        String body = "2||SUBSCRIBE|" + eventType + "||||^";
        return String.format("%05d|5|%s", body.length(), body);
    }

    public static String buildPreset(int pumpId, String presetType, String value,
                                     int hose, double unitPrice, String orderId,
                                     String customerId, String plate,
                                     String priceList, String paymentMethod) {
        String hoseWithPrice = hose + "@" + String.format("%.3f", unitPrice);

        String payIn = "OV=" + (orderId != null ? orderId : "")
            + "~CLI=" + (customerId != null ? customerId : "FINAL")
            + "~PLC=" + (plate      != null ? plate      : "")
            + "~LISTA=" + (priceList != null ? priceList : "STANDARD");

        String params = "TY=" + presetType
            + "|VA=" + value
            + "|HO=" + hoseWithPrice
            + "|PAY_TY=" + paymentMethod
            + "|PAY_IN=" + payIn
            + "|FTS=YES";

        return build("REQ_PUMP_PRESET_ID_" + String.format("%03d", pumpId), params);
    }

    public static String buildPumpStatusRequest(int pumpId) {
        if (pumpId == 0) {
            return build("REQ_PUMP_STATUS_ID_000", "");
        }
        return build("REQ_PUMP_STATUS_ID_" + String.format("%03d", pumpId), "");
    }

    public static String buildClearPreset(int pumpId) {
        return build("REQ_PUMP_CLEAR_PRESET_ID_" + String.format("%03d", pumpId), "");
    }

    public static String buildStop(int pumpId) {
        return build("REQ_PUMP_STOP_ID_" + String.format("%03d", pumpId), "PA=1");
    }

    public static String buildStopAll() {
        return build("REQ_PUMP_STOP_ID_000", "PA=1");
    }

    public static String buildClearStop(int pumpId) {
        return build("REQ_PUMP_CLEAR_STOP_ID_" + String.format("%03d", pumpId), "");
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
}
