package com.powerfin.pos.bridge.print;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class PrinterConfigTest {

    @Test
    void defaultPolicyIsAsk() {
        PrinterConfig config = new PrinterConfig("ASK");
        assertEquals(PrinterConfig.Policy.ASK, config.getPolicy());
    }

    @Test
    void policyAlways() {
        PrinterConfig config = new PrinterConfig("ALWAYS");
        assertEquals(PrinterConfig.Policy.ALWAYS, config.getPolicy());
    }

    @Test
    void policyNever() {
        PrinterConfig config = new PrinterConfig("NEVER");
        assertEquals(PrinterConfig.Policy.NEVER, config.getPolicy());
    }

    @Test
    void policyCaseInsensitive() {
        PrinterConfig config = new PrinterConfig("always");
        assertEquals(PrinterConfig.Policy.ALWAYS, config.getPolicy());
    }

    @Test
    void invalidPolicyDefaultsToAsk() {
        PrinterConfig config = new PrinterConfig("INVALID");
        assertEquals(PrinterConfig.Policy.ASK, config.getPolicy());
    }

    @Test
    void updatePolicy() {
        PrinterConfig config = new PrinterConfig("ASK");
        config.updatePolicy("ALWAYS");
        assertEquals(PrinterConfig.Policy.ALWAYS, config.getPolicy());
    }

    @Test
    void updatePolicyCaseInsensitive() {
        PrinterConfig config = new PrinterConfig("ASK");
        config.updatePolicy("never");
        assertEquals(PrinterConfig.Policy.NEVER, config.getPolicy());
    }
}
