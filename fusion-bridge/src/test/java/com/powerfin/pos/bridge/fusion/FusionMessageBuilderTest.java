package com.powerfin.pos.bridge.fusion;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class FusionMessageBuilderTest {

    @Test
    void buildEcho() {
        String result = FusionMessageBuilder.buildEcho();
        assertEquals("00012|5|2||ECHO||||^", result);
    }

    @Test
    void buildPumpStatusRequestAll() {
        String result = FusionMessageBuilder.buildPumpStatusRequest(0);
        assertEquals("00035|5|2||POST|REQ_PUMP_STATUS_ID_000||||^", result);
    }

    @Test
    void buildPumpStatusRequestSingle() {
        String result = FusionMessageBuilder.buildPumpStatusRequest(1);
        assertTrue(result.contains("REQ_PUMP_STATUS_ID_001"));
    }

    @Test
    void buildSubscribe() {
        String result = FusionMessageBuilder.buildSubscribe("EVT_PUMP_STATUS_CHANGE_ID_000");
        assertTrue(result.contains("SUBSCRIBE"));
        assertTrue(result.contains("EVT_PUMP_STATUS_CHANGE_ID_000"));
    }

    @Test
    void lenFieldIsCorrectForEcho() {
        String echo = FusionMessageBuilder.buildEcho();
        assertEquals("00012", echo.substring(0, 5));

        // The len field should equal the length from <version> to ^ inclusive
        // "00012|5|" is 8 chars — body starts at index 8
        String body = echo.substring(8);
        assertEquals(12, body.length());
        assertEquals(Integer.parseInt(echo.substring(0, 5)), body.length());
    }

    @Test
    void lenFieldIsCorrectForStatusRequest() {
        String msg = FusionMessageBuilder.build("REQ_PUMP_STATUS_ID_000", "");
        String lenStr = msg.substring(0, 5);

        // Parse len and verify against body length
        int expectedLen = Integer.parseInt(lenStr);
        String body = msg.substring(8); // skip "<len>|5|"
        assertEquals(expectedLen, body.length());
    }

    @Test
    void lenFieldIsCorrectForPreset() {
        String msg = FusionMessageBuilder.buildPreset(
            1, "MONEY", "50.00", 1, 9.990,
            "OV-001", "0912345678", "ABC-1234", "VIP", "EFECTIVO"
        );

        String lenStr = msg.substring(0, 5);
        int expectedLen = Integer.parseInt(lenStr);
        String body = msg.substring(8);
        assertEquals(expectedLen, body.length());

        // Verify key components
        assertTrue(msg.contains("REQ_PUMP_PRESET_ID_001"));
        assertTrue(msg.contains("TY=MONEY"));
        assertTrue(msg.contains("VA=50.00"));
        assertTrue(msg.contains("HO=1@9.990"));
        assertTrue(msg.contains("PAY_TY=EFECTIVO"));
        assertTrue(msg.contains("PAY_IN=OV=OV-001~CLI=0912345678~PLC=ABC-1234~LISTA=VIP"));
        assertTrue(msg.contains("FTS=YES"));
        assertTrue(msg.endsWith("|^"));
    }

    @Test
    void buildPresetWithNullCustomer() {
        String msg = FusionMessageBuilder.buildPreset(
            2, "VOLUME", "FULL", 2, 1.100,
            "OV-002", null, null, null, "TARJETA"
        );

        assertTrue(msg.contains("CLI=FINAL"));
        assertTrue(msg.contains("PLC="));
        assertTrue(msg.contains("LISTA=STANDARD"));
        assertTrue(msg.contains("PAY_TY=TARJETA"));
    }

    @Test
    void buildPresetWithVolumeType() {
        String msg = FusionMessageBuilder.buildPreset(
            1, "VOLUME", "10.000", 1, 1.500,
            "OV-003", "123", "", "VIP", "CREDITO"
        );

        assertTrue(msg.contains("TY=VOLUME"));
        assertTrue(msg.contains("VA=10.000"));
        assertTrue(msg.contains("HO=1@1.500"));
    }

    @Test
    void buildLock() {
        String msg = FusionMessageBuilder.buildLock("185", "OV-001");
        assertTrue(msg.contains("REQ_PAYMENT_TRANSACTION_LOCK"));
        assertTrue(msg.contains("SA=185"));
        assertTrue(msg.contains("LID=OV-001"));
        assertTrue(msg.contains("TMO=10"));
    }

    @Test
    void buildClearSale() {
        String msg = FusionMessageBuilder.buildClearSale("185", "OV-001", "EFECTIVO");
        assertTrue(msg.contains("REQ_PAYMENT_CLEAR_SALE"));
        assertTrue(msg.contains("SA=185"));
        assertTrue(msg.contains("TY=EFECTIVO"));
    }

    @Test
    void buildUnlock() {
        String msg = FusionMessageBuilder.buildUnlock("185", "OV-001");
        assertTrue(msg.contains("REQ_PAYMENT_TRANSACTION_UNLOCK"));
        assertTrue(msg.contains("SA=185"));
    }

    @Test
    void buildStop() {
        String msg = FusionMessageBuilder.buildStop(1);
        assertTrue(msg.contains("REQ_PUMP_STOP_ID_001"));
        assertTrue(msg.contains("PA=1"));
    }

    @Test
    void buildStopAll() {
        String msg = FusionMessageBuilder.buildStopAll();
        assertTrue(msg.contains("REQ_PUMP_STOP_ID_000"));
    }

    @Test
    void buildClearPreset() {
        String msg = FusionMessageBuilder.buildClearPreset(1);
        assertTrue(msg.contains("REQ_PUMP_CLEAR_PRESET_ID_001"));
    }

    @Test
    void buildClearStop() {
        String msg = FusionMessageBuilder.buildClearStop(1);
        assertTrue(msg.contains("REQ_PUMP_CLEAR_STOP_ID_001"));
    }

    @Test
    void buildWithCustomDestinationAndOrigin() {
        String msg = FusionMessageBuilder.build("REQ_PUMP_STATUS_ID_001", "",
            "192.168.1.100", "FusionBridge");
        assertTrue(msg.contains("REQ_PUMP_STATUS_ID_001"));
        assertTrue(msg.contains("|192.168.1.100|FusionBridge|"));
    }

    @Test
    void allMessagesEndWithTerminator() {
        assertTrue(FusionMessageBuilder.buildEcho().endsWith("^"));
        assertTrue(FusionMessageBuilder.buildPumpStatusRequest(0).endsWith("^"));
        assertTrue(FusionMessageBuilder.buildSubscribe("TEST").endsWith("^"));
        assertTrue(FusionMessageBuilder.build("TEST", "P=V").endsWith("^"));
        assertTrue(FusionMessageBuilder.buildPreset(1, "MONEY", "10", 1, 1.0,
            "OV-1", null, null, null, "CASH").endsWith("^"));
        assertTrue(FusionMessageBuilder.buildLock("1", "2").endsWith("^"));
        assertTrue(FusionMessageBuilder.buildClearSale("1", "2", "CASH").endsWith("^"));
        assertTrue(FusionMessageBuilder.buildUnlock("1", "2").endsWith("^"));
        assertTrue(FusionMessageBuilder.buildStop(1).endsWith("^"));
        assertTrue(FusionMessageBuilder.buildStopAll().endsWith("^"));
        assertTrue(FusionMessageBuilder.buildClearPreset(1).endsWith("^"));
        assertTrue(FusionMessageBuilder.buildClearStop(1).endsWith("^"));
    }

    @Test
    void lenFieldIsAlwaysFiveDigits() {
        String echo = FusionMessageBuilder.buildEcho();
        assertTrue(echo.substring(0, 5).matches("\\d{5}"));

        String preset = FusionMessageBuilder.buildPreset(1, "MONEY", "50.00", 1, 9.990,
            "OV-001", "0912345678", "ABC-1234", "VIP", "EFECTIVO");
        assertTrue(preset.substring(0, 5).matches("\\d{5}"));
    }
}
