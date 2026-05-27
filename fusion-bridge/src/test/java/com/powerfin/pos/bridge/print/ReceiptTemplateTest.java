package com.powerfin.pos.bridge.print;

import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class ReceiptTemplateTest {

    private TemplateRenderer renderer;

    @BeforeEach
    void setUp() {
        renderer = new TemplateRenderer("/tmp/test-receipt-template-" + System.currentTimeMillis() + ".txt");
        renderer.init();
    }

    @Test
    void defaultTemplateIsNotEmpty() {
        String tpl = renderer.getTemplate();
        assertNotNull(tpl);
        assertFalse(tpl.isBlank());
        assertTrue(tpl.contains("TOTAL"), "Default template should contain TOTAL");
        assertTrue(tpl.contains("[CUT]"), "Default template should contain CUT directive");
    }

    @Test
    void render_producesNonEmptyBytes() {
        byte[] receipt = renderer.render(minimalData());

        assertNotNull(receipt);
        assertTrue(receipt.length > 0);
    }

    @Test
    void render_substitutesPlaceholder() {
        ReceiptBuilder.FuelReceiptData data = minimalData();
        data.locationName = "GASOLINERA TEST";

        byte[] receipt = renderer.render(data);
        String text = new String(receipt, java.nio.charset.StandardCharsets.UTF_8);

        assertTrue(text.contains("GASOLINERA TEST"));
    }

    @Test
    void render_includesCutCommand() {
        byte[] receipt = renderer.render(minimalData());

        boolean hasCut = containsSequence(receipt, new byte[] { 0x1D, 0x56 });
        assertTrue(hasCut, "Receipt must contain GS V (cut) command");
    }

    @Test
    void render_includesBoldCommands() {
        byte[] receipt = renderer.render(minimalData());

        // Bold ON: ESC ! 0x08
        boolean hasBold = containsSequence(receipt, new byte[] { 0x1B, '!', 0x08 });
        assertTrue(hasBold, "Receipt must contain bold ON for TOTAL line");
    }

    @Test
    void render_includesCenterAlign() {
        byte[] receipt = renderer.render(minimalData());

        // Center align: ESC a 0x01
        boolean hasCenter = containsSequence(receipt, new byte[] { 0x1B, 'a', 0x01 });
        assertTrue(hasCenter, "Receipt must contain center align for header");
    }

    @Test
    void render_conditionalCustomerBlock_visibleWhenCustomerPresent() {
        ReceiptBuilder.FuelReceiptData data = minimalData();
        data.customerName = "Juan Pérez";

        byte[] receipt = renderer.render(data);
        String text = new String(receipt, java.nio.charset.StandardCharsets.UTF_8);

        assertTrue(text.contains("Juan Pérez"),
                "Customer block should be visible when customerName is set");
    }

    @Test
    void render_conditionalCustomerBlock_hiddenWhenCustomerAbsent() {
        ReceiptBuilder.FuelReceiptData data = minimalData();
        data.customerName = null;

        byte[] receipt = renderer.render(data);
        String text = new String(receipt, java.nio.charset.StandardCharsets.UTF_8);

        assertFalse(text.contains("Cliente:"),
                "Customer block should be hidden when no customerName");
    }

    @Test
    void render_conditionalInvoiceBlock_visibleWhenInvoicePresent() {
        ReceiptBuilder.FuelReceiptData data = minimalData();
        data.invoiceId = "001-001-000001234";

        byte[] receipt = renderer.render(data);
        String text = new String(receipt, java.nio.charset.StandardCharsets.UTF_8);

        assertTrue(text.contains("001-001-000001234"),
                "Invoice block should be visible when invoiceId is set");
    }

    @Test
    void render_conditionalInvoiceBlock_hiddenWhenInvoiceAbsent() {
        ReceiptBuilder.FuelReceiptData data = minimalData();
        data.invoiceId = null;

        byte[] receipt = renderer.render(data);
        String text = new String(receipt, java.nio.charset.StandardCharsets.UTF_8);

        assertFalse(text.contains("Factura:"),
                "Invoice block should be hidden when no invoiceId");
    }

    @Test
    void saveAndLoadTemplate() throws IOException {
        String custom = "[CENTER][BOLD]MI GASOLINERA[/BOLD][/CENTER]\n[CUT]";

        renderer.saveTemplate(custom);

        // Template should update in memory
        assertEquals(custom, renderer.getTemplate());

        // Render should use the new template
        byte[] receipt = renderer.render(minimalData());
        String text = new String(receipt, java.nio.charset.StandardCharsets.UTF_8);

        assertTrue(text.contains("MI GASOLINERA"));
        assertFalse(text.contains("TOTAL"), "Old template content should not appear");
    }

    @Test
    void resolve_replacesAllKnownPlaceholders() {
        ReceiptBuilder.FuelReceiptData data = new ReceiptBuilder.FuelReceiptData();
        data.locationName = "LOC";
        data.locationAddress = "ADDR";
        data.locationRuc = "RUC123";
        data.date = "01/01";
        data.time = "12:00";
        data.dispenserId = 99;
        data.hoseId = 7;
        data.grade = "DIESEL";
        data.volume = "100.00";
        data.unitPrice = "0.75";
        data.amount = "75.00";
        data.paymentMethod = "QR";
        data.customerName = "Cliente";
        data.plate = "PLACA";
        data.invoiceId = "INV";
        data.invoiceAuth = "AUTH";

        // Use a line with all placeholders
        String line = "{{location_name}}|{{dispenser_id}}|{{grade}}|{{volume}}|{{amount}}|{{payment_method}}|{{customer_name}}|{{invoice_id}}";
        String resolved = renderer.resolve(line, data);

        assertTrue(resolved.contains("LOC"));
        assertTrue(resolved.contains("99"));
        assertTrue(resolved.contains("DIESEL"));
        assertTrue(resolved.contains("100.00"));
        assertTrue(resolved.contains("75.00"));
        assertTrue(resolved.contains("QR"));
    }

    @Test
    void resolve_nullFieldsBecomeEmpty() {
        ReceiptBuilder.FuelReceiptData data = new ReceiptBuilder.FuelReceiptData();
        data.locationName = null;

        String resolved = renderer.resolve("{{location_name}}|{{customer_name}}", data);

        assertEquals("GASOLINERA|", resolved);
    }

    // ── Helpers ──────────────────────────────────────────────

    private ReceiptBuilder.FuelReceiptData minimalData() {
        ReceiptBuilder.FuelReceiptData data = new ReceiptBuilder.FuelReceiptData();
        data.locationName = "TEST";
        data.dispenserId = 1;
        data.hoseId = 1;
        data.grade = "SUPER";
        data.volume = "10.00";
        data.unitPrice = "1.00";
        data.amount = "10.00";
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
