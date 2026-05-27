package com.powerfin.pos.bridge.fusion;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class FusionMessageTest {

    @Test
    void parseEchoRequest() {
        String raw = "00012|5|2||ECHO||||^";
        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals("00012", msg.len);
        assertEquals("5", msg.crypt);
        assertEquals("2", msg.version);
        assertEquals("", msg.userId);
        assertEquals("ECHO", msg.msgType);
        assertEquals("", msg.eventType);
        assertEquals("", msg.destination);
        assertEquals("", msg.origin);
        assertTrue(msg.params.isEmpty());
        assertEquals(raw, msg.raw);
    }

    @Test
    void parseEchoResponse() {
        String raw = "00031|5|2||ECHO||192.168.1.100:55790||^";
        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals("ECHO", msg.msgType);
        assertEquals("", msg.eventType);
        assertEquals("192.168.1.100:55790", msg.destination);
        assertEquals("", msg.origin);
    }

    @Test
    void parsePumpStatusRequest() {
        String raw = "00035|5|2||POST|REQ_PUMP_STATUS_ID_000||||^";
        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals("POST", msg.msgType);
        assertEquals("REQ_PUMP_STATUS_ID_000", msg.eventType);
        assertEquals(0, msg.getPumpNumber());
    }

    @Test
    void parsePumpStatusResponse() {
        String raw = "00088|5|2|GUEST|POST|EVT_PUMP_STATUS_CHANGE_ID_001"
            + "|192.168.1.100:35378|127.0.0.1:50602"
            + "|SU=|ST=CLOSED|PR=0.00|HN=2|__PP=1|^";

        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals("POST", msg.msgType);
        assertEquals("EVT_PUMP_STATUS_CHANGE_ID_001", msg.eventType);
        assertEquals("192.168.1.100:35378", msg.destination);
        assertEquals("127.0.0.1:50602", msg.origin);
        assertEquals(1, msg.getPumpNumber());

        assertEquals("", msg.params.get("SU"));
        assertEquals("CLOSED", msg.params.get("ST"));
        assertEquals("0.00", msg.params.get("PR"));
        assertEquals("2", msg.params.get("HN"));
    }

    @Test
    void parsePumpStatusIdleAuthorized() {
        String raw = "00084|5|2|GUEST|POST|EVT_PUMP_STATUS_CHANGE_ID_001"
            + "|192.168.1.100:35378|127.0.0.1:50602"
            + "|SU=MONEY_PRESET|ST=AUTHORIZED|PR=50.00|HN=2|^";

        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals(1, msg.getPumpNumber());
        assertEquals("AUTHORIZED", msg.params.get("ST"));
        assertEquals("MONEY_PRESET", msg.params.get("SU"));
        assertEquals("50.00", msg.params.get("PR"));
    }

    @Test
    void parseNewTransaction() {
        String raw = "00347|5|2|GUEST|POST|EVT_PUMP_NEW_TRANSACTION"
            + "||"
            + "|SA=185|PM=1|HO=1|GR=1|VO=3.850|AM=38.46|PU=9.990"
            + "|PR=50.00|TY=1|DA=20240421|TI=143022"
            + "|PAY_TY=EFECTIVO|PAY_IN=OV=OV-20240421-001~CLI=0912345678~PLC=ABC-1234"
            + "|FCR=NormalCompletion|SID=1|^";

        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals("EVT_PUMP_NEW_TRANSACTION", msg.eventType);
        assertEquals("185", msg.params.get("SA"));
        assertEquals("1", msg.params.get("PM"));
        assertEquals("3.850", msg.params.get("VO"));
        assertEquals("38.46", msg.params.get("AM"));
        assertEquals("NormalCompletion", msg.params.get("FCR"));
    }

    @Test
    void extractPayInFieldFromTransaction() {
        String raw = "00347|5|2|GUEST|POST|EVT_PUMP_NEW_TRANSACTION"
            + "||"
            + "|SA=185|PM=1|PAY_IN=OV=OV-20240421-001~CLI=0912345678~PLC=ABC-1234"
            + "|^";

        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals("OV-20240421-001", msg.getPayInField("OV"));
        assertEquals("0912345678", msg.getPayInField("CLI"));
        assertEquals("ABC-1234", msg.getPayInField("PLC"));
        assertNull(msg.getPayInField("NONEXISTENT"));
    }

    @Test
    void extractPayInFieldStatic() {
        String payIn = "OV=OV-001~CLI=0912345678~LISTA=VIP~PLC=ABC-1234";

        assertEquals("OV-001", FusionMessage.extractPayInField(payIn, "OV"));
        assertEquals("0912345678", FusionMessage.extractPayInField(payIn, "CLI"));
        assertEquals("VIP", FusionMessage.extractPayInField(payIn, "LISTA"));
        assertEquals("ABC-1234", FusionMessage.extractPayInField(payIn, "PLC"));
        assertNull(FusionMessage.extractPayInField(payIn, "ZZZ"));
        assertNull(FusionMessage.extractPayInField(null, "OV"));
        assertNull(FusionMessage.extractPayInField("", "OV"));
    }

    @Test
    void parseDeliveryProgress() {
        String raw = "00130|5|2|GUEST|POST|EVT_PUMP_DELIVERY_PROGRESS_ID_001"
            + "||"
            + "|AM=15.50|VO=1.551|AMS=34.50|PU=9.990|HO=1|TS=1713729622.123|^";

        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals(1, msg.getPumpNumber());
        assertEquals("15.50", msg.params.get("AM"));
        assertEquals("1.551", msg.params.get("VO"));
    }

    @Test
    void parseFromBytes() {
        byte[] rawBytes = "00012|5|2||ECHO||||^".getBytes();
        FusionMessage msg = FusionMessage.parse(rawBytes);

        assertEquals("ECHO", msg.msgType);
    }

    @Test
    void parseMessageWithoutTerminator() {
        FusionMessage msg = FusionMessage.parse("00012|5|2||ECHO||||");

        assertEquals("ECHO", msg.msgType);
    }

    @Test
    void parseMinimalMessage() {
        FusionMessage msg = FusionMessage.parse("00010|5|2|A|B|C|^");

        assertEquals("A", msg.userId);
        assertEquals("B", msg.msgType);
        assertEquals("C", msg.eventType);
    }

    @Test
    void getPumpNumberFromStatusChange() {
        FusionMessage msg = new FusionMessage();
        msg.eventType = "EVT_PUMP_STATUS_CHANGE_ID_001";
        assertEquals(1, msg.getPumpNumber());

        msg.eventType = "EVT_PUMP_STATUS_CHANGE_ID_004";
        assertEquals(4, msg.getPumpNumber());

        msg.eventType = "EVT_PUMP_STATUS_CHANGE_ID_000";
        assertEquals(0, msg.getPumpNumber());
    }

    @Test
    void getPumpNumberEdgeCases() {
        FusionMessage msg = new FusionMessage();

        msg.eventType = null;
        assertEquals(0, msg.getPumpNumber());

        msg.eventType = "EVT_PUMP_NEW_TRANSACTION";
        assertEquals(0, msg.getPumpNumber()); // Not a number in last position

        msg.eventType = "EVT_PUMP_STATUS_CHANGE_ID_XYZ";
        assertEquals(0, msg.getPumpNumber()); // Not numeric
    }

    @Test
    void parseVersionResponse() {
        String raw = "00187|5|2||POST|RES_GET_FUSION_VERSION"
            + "|"
            + "|OS=Windows|MAC=68:1d:ef:31:53:86|HWV=V2|BIN=Rel-5.19.1|^";

        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals("RES_GET_FUSION_VERSION", msg.eventType);
        assertEquals("Windows", msg.params.get("OS"));
        assertEquals("68:1d:ef:31:53:86", msg.params.get("MAC"));
        assertEquals("Rel-5.19.1", msg.params.get("BIN"));
    }

    @Test
    void parseConfigGral() {
        String raw = "00263|5|2||POST|RES_FCRT_GET_GRAL_CONFIG"
            + "|"
            + "|SNR=3|SNA=NEOPAUTE|CNY=EC|MUD=DOLLARS|DCV=3|DCP=3|DCM=2|^";

        FusionMessage msg = FusionMessage.parse(raw);

        assertEquals("NEOPAUTE", msg.params.get("SNA"));
        assertEquals("EC", msg.params.get("CNY"));
        assertEquals("DOLLARS", msg.params.get("MUD"));
    }
}
