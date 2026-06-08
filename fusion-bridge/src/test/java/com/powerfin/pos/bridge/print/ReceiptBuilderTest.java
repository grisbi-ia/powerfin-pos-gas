package com.powerfin.pos.bridge.print;

import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class ReceiptBuilderTest {

    private static TemplateRenderer renderer;
    private ReceiptBuilder builder;

    @BeforeAll
    static void initRenderer() {
        renderer = new TemplateRenderer("/tmp/test-receipt-template.txt");
        renderer.init();
    }

    @BeforeEach
    void setUp() {
        builder = new ReceiptBuilder(renderer);
    }

    @Test
    void buildFuelReceipt_generatesNonEmptyBytes() throws IOException {
        ReceiptBuilder.FuelReceiptData data = sampleData();

        byte[] receipt = builder.buildFuelReceipt(data);

        assertNotNull(receipt);
        assertTrue(receipt.length > 0, "Receipt should not be empty");
    }

    @Test
    void buildFuelReceipt_containsLocationName() throws IOException {
        ReceiptBuilder.FuelReceiptData data = sampleData();
        data.locationName = "GASOLINERA NEOPAUTE";

        byte[] receipt = builder.buildFuelReceipt(data);
        String text = new String(receipt, "UTF-8");

        assertTrue(text.contains("NEOPAUTE"),
                "Receipt should contain location name");
    }

    @Test
    void buildFuelReceipt_containsTotalAmount() throws IOException {
        ReceiptBuilder.FuelReceiptData data = sampleData();

        byte[] receipt = builder.buildFuelReceipt(data);
        String text = new String(receipt, "UTF-8");

        assertTrue(text.contains("TOTAL"),
                "Receipt should contain TOTAL label");
    }

    @Test
    void buildFuelReceipt_containsCutCommand() throws IOException {
        ReceiptBuilder.FuelReceiptData data = sampleData();

        byte[] receipt = builder.buildFuelReceipt(data);

        boolean hasCut = containsSequence(receipt, new byte[] { 0x1D, 0x56 });
        assertTrue(hasCut, "Receipt should contain paper cut command (GS V)");
    }

    @Test
    void buildFuelReceipt_withOptionalFields() throws IOException {
        ReceiptBuilder.FuelReceiptData data = sampleData();
        data.customerName = "Juan Pérez";
        data.plate = "ABC-1234";
        data.invoiceId = "001-001-000001234";
        data.invoiceAuth = "20240421143247";

        byte[] receipt = builder.buildFuelReceipt(data);
        String text = new String(receipt, "UTF-8");

        assertTrue(text.contains("Juan"));
        assertTrue(text.contains("ABC-1234"));
        assertTrue(text.contains("001-001-000001234"));
    }

    @Test
    void buildFuelReceipt_minimalDataDoesNotCrash() throws IOException {
        ReceiptBuilder.FuelReceiptData data = new ReceiptBuilder.FuelReceiptData();
        data.dispenserId = 1;
        data.hoseId = 1;
        data.volume = "0.00";
        data.unitPrice = "0.00";
        data.amount = "0.00";

        byte[] receipt = builder.buildFuelReceipt(data);

        assertNotNull(receipt);
        assertTrue(receipt.length > 0);
    }

    @Test
    void fromMap_parsesFlatFuelData() {
        java.util.Map<String, Object> request = java.util.Map.of(
                "type", "FUEL_RECEIPT",
                "dispenser_id", 1,
                "fuel_data", java.util.Map.of(
                        "locationName", "TEST",
                        "dispenserId", 2,
                        "hoseId", 3,
                        "grade", "SUPER",
                        "volume", "10.000",
                        "unitPrice", "1.100",
                        "amount", "11.00",
                        "paymentMethod", "EFECTIVO"
                )
        );

        ReceiptBuilder.FuelReceiptData data =
                ReceiptBuilder.FuelReceiptData.fromMap(request);

        assertEquals("TEST", data.locationName);
        assertEquals(2, data.dispenserId);
        assertEquals(3, data.hoseId);
        assertEquals("SUPER", data.grade);
        assertEquals("10.000", data.volume);
        assertEquals("1.100", data.unitPrice);
        assertEquals("11.00", data.amount);
        assertEquals("EFECTIVO", data.paymentMethod);
    }

    @Test
    void fromMap_dispenserIdFromTopLevel() {
        java.util.Map<String, Object> request = java.util.Map.of(
                "type", "FUEL_RECEIPT",
                "dispenser_id", 5,
                "fuel_data", java.util.Map.of()
        );

        ReceiptBuilder.FuelReceiptData data =
                ReceiptBuilder.FuelReceiptData.fromMap(request);

        assertEquals(5, data.dispenserId);
    }

    @Test
    void isPrinterReachable_unreachableReturnsFalse() {
        boolean reachable = builder.isPrinterReachable("192.0.2.1", 9100);
        assertFalse(reachable, "Non-existent printer should not be reachable");
    }

    // ── Helpers ──────────────────────────────────────────────

    private ReceiptBuilder.FuelReceiptData sampleData() {
        ReceiptBuilder.FuelReceiptData data = new ReceiptBuilder.FuelReceiptData();
        data.locationName = "GASOLINERA NEOPAUTE";
        data.locationAddress = "Av. Principal 123";
        data.locationRuc = "0190012345001";
        data.date = "21/04/2024";
        data.time = "14:32:47";
        data.dispenserId = 1;
        data.hoseId = 1;
        data.grade = "Gasolina Super";
        data.volume = "45.455";
        data.unitPrice = "1.100";
        data.amount = "50.00";
        data.paymentMethod = "EFECTIVO";
        return data;
    }

    private boolean containsSequence(byte[] haystack, byte[] needle) {
        for (int i = 0; i <= haystack.length - needle.length; i++) {
            boolean match = true;
            for (int j = 0; j < needle.length; j++) {
                if (haystack[i + j] != needle[j]) {
                    match = false;
                    break;
                }
            }
            if (match) return true;
        }
        return false;
    }
}
