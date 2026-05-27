package com.powerfin.pos.bridge.fusion;

import java.util.LinkedHashMap;
import java.util.Map;

public class FusionMessage {

    public String raw;
    public String len;
    public String crypt;
    public String version;
    public String userId;
    public String msgType;
    public String eventType;
    public String destination;
    public String origin;
    public Map<String, String> params = new LinkedHashMap<>();

    public static FusionMessage parse(String raw) {
        FusionMessage msg = new FusionMessage();
        msg.raw = raw.trim();

        String content = msg.raw.endsWith("^")
            ? msg.raw.substring(0, msg.raw.length() - 1)
            : msg.raw;

        String[] parts = content.split("\\|", -1);
        if (parts.length < 6) return msg;

        msg.len         = parts[0];
        msg.crypt       = parts[1];
        msg.version     = parts[2];
        msg.userId      = parts[3];
        msg.msgType     = parts[4];
        msg.eventType   = parts[5];

        // destination is always at index 6 if present
        msg.destination = parts.length > 6 ? parts[6] : "";

        // origin: if index 7 has KEY=VALUE pattern, treat it as a param,
        // since origin can be empty in messages where both dest and origin are omitted
        int paramStartIdx = 8;
        if (parts.length > 7) {
            if (parts[7].contains("=")) {
                msg.origin = "";
                paramStartIdx = 7;
            } else {
                msg.origin = parts[7];
            }
        } else {
            msg.origin = "";
        }

        for (int i = paramStartIdx; i < parts.length; i++) {
            if (parts[i].isEmpty()) continue;
            int eq = parts[i].indexOf('=');
            if (eq > 0) {
                msg.params.put(parts[i].substring(0, eq), parts[i].substring(eq + 1));
            }
        }
        return msg;
    }

    public static FusionMessage parse(byte[] rawBytes) {
        return parse(new String(rawBytes));
    }

    public int getPumpNumber() {
        if (eventType == null) return 0;
        try {
            String[] parts = eventType.split("_");
            return Integer.parseInt(parts[parts.length - 1]);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    public static String extractPayInField(String payIn, String field) {
        if (payIn == null || payIn.isEmpty()) return null;
        for (String part : payIn.split("~")) {
            int eq = part.indexOf('=');
            if (eq > 0 && part.substring(0, eq).equals(field)) {
                return part.substring(eq + 1);
            }
        }
        return null;
    }

    public String getPayInField(String field) {
        return extractPayInField(params.getOrDefault("PAY_IN", ""), field);
    }
}
