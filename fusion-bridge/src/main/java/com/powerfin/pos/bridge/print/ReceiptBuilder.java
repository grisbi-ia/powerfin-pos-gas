package com.powerfin.pos.bridge.print;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.Map;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

/**
 * Builds fuel receipts using a configurable template.
 * Delegates ESC/POS rendering to {@link TemplateRenderer}.
 */
@ApplicationScoped
public class ReceiptBuilder {

    private final TemplateRenderer renderer;

    @Inject
    public ReceiptBuilder(TemplateRenderer renderer) {
        this.renderer = renderer;
    }

    /**
     * Renders a fuel receipt using the current template.
     */
    public byte[] buildFuelReceipt(FuelReceiptData data) throws IOException {
        return renderer.render(data);
    }

    /**
     * Checks if a printer is reachable via TCP.
     */
    public boolean isPrinterReachable(String ip, int port) {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress(ip, port), 2_000);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    // ── Data holder ─────────────────────────────────────────

    public static class FuelReceiptData {
        public String locationName;
        public String locationAddress;
        public String locationRuc;
        public String date;
        public String time;
        public String orderId;
        public int dispenserId;
        public int hoseId;
        public String grade;
        public String volume;
        public String unitPrice;
        public String amount;
        public String paymentMethod;
        public String customerName;
        public String plate;
        public String invoiceId;
        public String invoiceAuth;

        @SuppressWarnings("unchecked")
        public static FuelReceiptData fromMap(Map<String, Object> request) {
            FuelReceiptData d = new FuelReceiptData();
            d.dispenserId = intParam(request, "dispenser_id", 1);

            Map<String, Object> fuel = (Map<String, Object>) request.get("fuel_data");
            if (fuel != null) {
                d.locationName = strParam(fuel, "location_name");
                d.locationAddress = strParam(fuel, "location_address");
                d.locationRuc = strParam(fuel, "location_ruc");
                d.date = strParam(fuel, "date");
                d.time = strParam(fuel, "time");
                d.orderId = strParam(fuel, "orderId");
                d.dispenserId = intParam(fuel, "dispenserId", d.dispenserId);
                d.hoseId = intParam(fuel, "hoseId", 1);
                d.grade = strParam(fuel, "grade");
                d.volume = strParam(fuel, "volume");
                d.unitPrice = strParam(fuel, "unitPrice");
                d.amount = strParam(fuel, "amount");
                d.paymentMethod = strParam(fuel, "paymentMethod");
                d.customerName = strParam(fuel, "customerName");
                d.plate = strParam(fuel, "plate");
                d.invoiceId = strParam(fuel, "invoiceId");
                d.invoiceAuth = strParam(fuel, "invoiceAuth");
            }

            return d;
        }

        private static String strParam(Map<String, Object> map, String key) {
            Object v = map.get(key);
            return v != null ? v.toString() : null;
        }

        private static int intParam(Map<String, Object> map, String key, int defaultVal) {
            Object v = map.get(key);
            if (v instanceof Number) return ((Number) v).intValue();
            if (v instanceof String) {
                try { return Integer.parseInt((String) v); } catch (NumberFormatException e) { }
            }
            return defaultVal;
        }
    }
}
