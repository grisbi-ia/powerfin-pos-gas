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
     * Renders a cash movement receipt using the cash template.
     */
    public byte[] buildCashMovementReceipt(CashMovementData data) throws IOException {
        return renderer.renderCashMovement(data);
    }

    /**
     * Renders a shift close receipt.
     */
    public byte[] buildShiftCloseReceipt(ShiftCloseData data) throws IOException {
        return renderer.renderShiftClose(data);
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
        public boolean isReprint;

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
                d.isReprint = Boolean.TRUE.equals(fuel.get("isReprint"));
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

    // ── Cash movement receipt data ─────────────────────────

    public static class CashMovementData {
        public String locationName;
        public String locationAddress;
        public String locationRuc;
        public String locationPhone;
        public String movementType;   // INGRESO, EGRESO, TRANSFERENCIA
        public String date;
        public String time;
        public String userName;
        public String amount;
        public String observation;
        public boolean isReprint;

        @SuppressWarnings("unchecked")
        public static CashMovementData fromMap(Map<String, Object> request) {
            CashMovementData d = new CashMovementData();

            // Accept both camelCase (POS) and snake_case
            Map<String, Object> data = (Map<String, Object>) request.get("cashData");
            if (data == null) {
                data = (Map<String, Object>) request.get("cash_data");
            }
            if (data == null) {
                data = request;
            }

            d.locationName = str(data, "locationName", str(data, "location_name", "GASOLINERA"));
            d.locationAddress = str(data, "locationAddress", str(data, "location_address", ""));
            d.locationRuc = str(data, "locationRuc", str(data, "location_ruc", ""));
            d.locationPhone = str(data, "locationPhone", str(data, "location_phone", ""));
            d.movementType = str(data, "movementType", str(data, "movement_type", ""));
            d.date = str(data, "date", "");
            d.time = str(data, "time", "");
            d.userName = str(data, "userName", str(data, "user_name", ""));
            d.amount = str(data, "amount", "0.00");
            d.observation = str(data, "observation", "");
            d.isReprint = Boolean.TRUE.equals(data.get("isReprint"));

            return d;
        }

        private static String str(Map<String, Object> map, String key, String def) {
            Object v = map.get(key);
            return v != null ? v.toString() : def;
        }
    }

    // ── Shift close receipt data ─────────────────────────

    public static class ShiftCloseData {
        public String locationName, locationAddress, locationRuc, locationPhone;
        public String date, time, userName;
        public String shiftId, openedAt, closedAt;
        public String openingCash;
        // Cash breakdown
        public String salesCash, salesCashCount;
        public String income, incomeCount;
        public String expense, expenseCount;
        public String deposits, depositsCount;
        public String transfersOut, transfersOutCount;
        public String transfersIn, transfersInCount;
        public String safeDrops, safeDropsCount;
        // Result
        public String surplus, shortage;
        public String totalCash, totalSales;
        // Non-cash sales (formatted as multi-line string)
        public String nonCashLines;

        @SuppressWarnings("unchecked")
        public static ShiftCloseData fromMap(Map<String, Object> request) {
            ShiftCloseData d = new ShiftCloseData();
            Map<String, Object> data = (Map<String, Object>) request.get("shiftData");
            if (data == null) data = request;

            d.locationName = str(data, "locationName", "GASOLINERA");
            d.locationAddress = str(data, "locationAddress", "");
            d.locationRuc = str(data, "locationRuc", "");
            d.locationPhone = str(data, "locationPhone", "");
            d.date = str(data, "date", "");
            d.time = str(data, "time", "");
            d.userName = str(data, "userName", "");
            d.shiftId = str(data, "shiftId", "");
            d.openedAt = str(data, "openedAt", "");
            d.closedAt = str(data, "closedAt", "");
            d.openingCash = str(data, "openingCash", "0.00");
            d.salesCash = str(data, "salesCash", "0.00");
            d.salesCashCount = str(data, "salesCashCount", "0");
            d.income = str(data, "income", "0.00");
            d.incomeCount = str(data, "incomeCount", "0");
            d.expense = str(data, "expense", "0.00");
            d.expenseCount = str(data, "expenseCount", "0");
            d.deposits = str(data, "deposits", "0.00");
            d.depositsCount = str(data, "depositsCount", "0");
            d.transfersOut = str(data, "transfersOut", "0.00");
            d.transfersOutCount = str(data, "transfersOutCount", "0");
            d.transfersIn = str(data, "transfersIn", "0.00");
            d.transfersInCount = str(data, "transfersInCount", "0");
            d.safeDrops = str(data, "safeDrops", "0.00");
            d.safeDropsCount = str(data, "safeDropsCount", "0");
            d.surplus = str(data, "surplus", "");
            d.shortage = str(data, "shortage", "");
            d.totalCash = str(data, "totalCash", "0.00");
            d.totalSales = str(data, "totalSales", "0.00");
            // Non-cash: format as "METODO (N): $ X.XX" lines
            java.util.List<Map<String, Object>> nonCash = (java.util.List<Map<String, Object>>) data.get("nonCashSales");
            if (nonCash != null && !nonCash.isEmpty()) {
                StringBuilder sb = new StringBuilder();
                for (Map<String, Object> nc : nonCash) {
                    String name = String.valueOf(nc.getOrDefault("method_name", nc.getOrDefault("methodName", "")));
                    String total = String.valueOf(nc.getOrDefault("total", "0"));
                    String count = String.valueOf(nc.getOrDefault("count", "0"));
                    if (!name.isEmpty()) sb.append(name).append(" (").append(count).append("): $ ").append(total).append("\n");
                }
                d.nonCashLines = sb.toString().trim();
            }
            return d;
        }

        private static String str(Map<String, Object> map, String key, String def) {
            Object v = map.get(key);
            return v != null ? v.toString() : def;
        }
    }
}
