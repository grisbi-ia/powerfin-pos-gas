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
        public String locationPhone;
        public String locationCity;
        public String locationProvince;
        public String locationCountry;
        public String fiscalRegime;
        public int sriEnvironment;
        public int emissionType;
        public String date;
        public String time;
        public String orderId;
        public int dispenserId;
        public int hoseId;
        public String grade;
        public String volume;
        public String unitPrice;
        public String priceWithoutSubsidy;
        public String subsidyPerUnit;
        public String subsidyAmount;
        public String amount;
        public String paymentMethod;
        public String customerName;
        public String customerId;
        public String customerAddress;
        public String customerPhone;
        public String customerEmail;
        public String plate;
        public String invoiceId;
        public String invoiceAuth;
        public String subtotal;
        public String taxLabel;
        public String taxAmount;
        public String unit;

        @SuppressWarnings("unchecked")
        public static FuelReceiptData fromMap(Map<String, Object> request) {
            FuelReceiptData d = new FuelReceiptData();

            // Accept both camelCase (POS/TypeScript) and dispenser_id (legacy)
            d.dispenserId = intParam(request, "dispenserId",
                    intParam(request, "dispenser_id", 1));

            // Accept both fuelData (POS) and fuel_data (legacy)
            Map<String, Object> fuel = (Map<String, Object>) request.get("fuelData");
            if (fuel == null) {
                fuel = (Map<String, Object>) request.get("fuel_data");
            }
            // Fallback: if no sub-object, read from top level (flat mode)
            if (fuel == null) {
                fuel = request;
            }

            if (fuel != null) {
                d.locationName = strParam(fuel, "locationName");
                d.locationAddress = strParam(fuel, "locationAddress");
                d.locationRuc = strParam(fuel, "locationRuc");
                d.locationPhone = strParam(fuel, "locationPhone");
                d.locationCity = strParam(fuel, "locationCity");
                d.locationProvince = strParam(fuel, "locationProvince");
                d.locationCountry = strParam(fuel, "locationCountry");
                d.fiscalRegime = strParam(fuel, "fiscalRegime");
                d.sriEnvironment = intParam(fuel, "sriEnvironment", 0);
                d.emissionType = intParam(fuel, "emissionType", 0);
                d.date = strParam(fuel, "date");
                d.time = strParam(fuel, "time");
                d.orderId = strParam(fuel, "orderId");
                d.dispenserId = intParam(fuel, "dispenserId", d.dispenserId);
                d.hoseId = intParam(fuel, "hoseId", 1);
                d.grade = strParam(fuel, "grade");
                d.volume = strParam(fuel, "volume");
                d.unitPrice = strParam(fuel, "unitPrice");
                d.priceWithoutSubsidy = strParam(fuel, "priceWithoutSubsidy");
                d.subsidyPerUnit = strParam(fuel, "subsidyPerUnit");
                d.subsidyAmount = strParam(fuel, "subsidyAmount");
                d.amount = strParam(fuel, "amount");
                d.paymentMethod = strParam(fuel, "paymentMethod");
                d.customerName = strParam(fuel, "customerName");
                d.customerId = strParam(fuel, "customerId");
                d.customerAddress = strParam(fuel, "customerAddress");
                d.customerPhone = strParam(fuel, "customerPhone");
                d.customerEmail = strParam(fuel, "customerEmail");
                d.plate = strParam(fuel, "plate");
                d.invoiceId = strParam(fuel, "invoiceId");
                d.invoiceAuth = strParam(fuel, "invoiceAuth");
                d.subtotal = strParam(fuel, "subtotal");
                d.taxLabel = strParam(fuel, "taxLabel");
                d.taxAmount = strParam(fuel, "taxAmount");
                d.unit = strParam(fuel, "unit");
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
