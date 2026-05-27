package com.powerfin.pos.bridge.print;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Map;

import org.junit.jupiter.api.Test;

class PrinterConfigTest {

    @Test
    void defaultPolicyIsAsk() {
        PrinterConfig config = new PrinterConfig("ASK", "/tmp/test-printer-nonexistent.json");
        config.init();
        assertEquals(PrinterConfig.Policy.ASK, config.getPolicy());
    }

    @Test
    void policyAlways() {
        PrinterConfig config = new PrinterConfig("ALWAYS", "/tmp/test-printer-nonexistent.json");
        config.init();
        assertEquals(PrinterConfig.Policy.ALWAYS, config.getPolicy());
    }

    @Test
    void policyNever() {
        PrinterConfig config = new PrinterConfig("NEVER", "/tmp/test-printer-nonexistent.json");
        config.init();
        assertEquals(PrinterConfig.Policy.NEVER, config.getPolicy());
    }

    @Test
    void policyCaseInsensitive() {
        PrinterConfig config = new PrinterConfig("always", "/tmp/test-printer-nonexistent.json");
        config.init();
        assertEquals(PrinterConfig.Policy.ALWAYS, config.getPolicy());
    }

    @Test
    void invalidPolicyDefaultsToAsk() {
        PrinterConfig config = new PrinterConfig("INVALID", "/tmp/test-printer-nonexistent.json");
        config.init();
        assertEquals(PrinterConfig.Policy.ASK, config.getPolicy());
    }

    @Test
    void seedsDefaultIslandsFromFallbackWhenNoConfigFile() {
        PrinterConfig config = new PrinterConfig("ASK", "/tmp/test-printer-nonexistent.json");
        config.init();

        // Default fallback: island1=192.168.1.31, island2=192.168.1.32
        assertEquals("192.168.1.31", config.getIp(1));
        assertEquals(9100, config.getPort(1));
        assertEquals("192.168.1.32", config.getIp(2));
        assertEquals(9100, config.getPort(2));
        assertEquals(2, config.getIslands().size());
    }

    @Test
    void islandLookupReturnsFallbackForUnknownIsland() {
        PrinterConfig config = new PrinterConfig("ASK", "/tmp/test-printer-nonexistent.json");
        config.init();

        // Island 99 doesn't exist → fallback to 192.168.1.31:9100
        assertEquals("192.168.1.31", config.getIp(99));
        assertEquals(9100, config.getPort(99));
    }

    @Test
    void updateFromMapChangesPolicy() {
        PrinterConfig config = new PrinterConfig("ASK",
                "/tmp/test-printer-policy-" + System.currentTimeMillis() + ".json");
        config.init();

        config.updateFromMap(Map.of("policy", "ALWAYS"));
        assertEquals(PrinterConfig.Policy.ALWAYS, config.getPolicy());
    }

    @Test
    void updateFromMapChangesIslandIp() {
        PrinterConfig config = new PrinterConfig("ASK",
                "/tmp/test-printer-ip-" + System.currentTimeMillis() + ".json");
        config.init();

        config.updateFromMap(Map.of(
                "islands", Map.of(
                        "1", Map.of("ip", "10.0.0.99")
                )
        ));

        assertEquals("10.0.0.99", config.getIp(1));
        // Island 2 unchanged
        assertEquals("192.168.1.32", config.getIp(2));
    }

    @Test
    void updateFromMapAddsNewIsland() {
        PrinterConfig config = new PrinterConfig("ASK",
                "/tmp/test-printer-add-" + System.currentTimeMillis() + ".json");
        config.init();

        config.updateFromMap(Map.of(
                "islands", Map.of(
                        "3", Map.of("ip", "10.0.0.33", "port", 9100)
                )
        ));

        assertEquals(3, config.getIslands().size());
        assertEquals("10.0.0.33", config.getIp(3));
        assertEquals(9100, config.getPort(3));
    }

    @Test
    void updateFromMapKeepsExistingIslandsIfNotMentioned() {
        // Use a fresh file that doesn't exist to avoid cross-test pollution
        PrinterConfig config = new PrinterConfig("ASK",
                "/tmp/test-printer-keeps-" + System.currentTimeMillis() + ".json");
        config.init();
        assertEquals(2, config.getIslands().size());

        // Only update island 1's IP
        config.updateFromMap(Map.of(
                "islands", Map.of(
                        "1", Map.of("ip", "10.0.0.99")
                )
        ));

        // Both islands still exist
        assertEquals(2, config.getIslands().size());
        assertEquals("10.0.0.99", config.getIp(1));
        assertEquals("192.168.1.32", config.getIp(2));
    }

    @Test
    void backwardCompat_getPrinterIp() {
        PrinterConfig config = new PrinterConfig("ASK", "/tmp/test-printer-nonexistent.json");
        config.init();

        // Old dispenser-based mapping still works: 1-2→island1, 3-4→island2
        assertEquals("192.168.1.31", config.getPrinterIp(1));
        assertEquals("192.168.1.31", config.getPrinterIp(2));
        assertEquals("192.168.1.32", config.getPrinterIp(3));
        assertEquals("192.168.1.32", config.getPrinterIp(4));
    }
}
