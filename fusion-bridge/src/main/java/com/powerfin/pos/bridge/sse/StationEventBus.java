package com.powerfin.pos.bridge.sse;

import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

import io.quarkus.logging.Log;
import io.smallrye.mutiny.Multi;
import io.smallrye.mutiny.operators.multi.processors.BroadcastProcessor;

public class StationEventBus {

    private final BroadcastProcessor<String> processor = BroadcastProcessor.create();
    private final CopyOnWriteArrayList<Runnable> connectionListeners = new CopyOnWriteArrayList<>();

    public void broadcast(String eventType, Map<String, Object> data) {
        StringBuilder sb = new StringBuilder();
        sb.append("event:").append(eventType).append("\n");
        sb.append("data:");
        appendJson(sb, data);
        sb.append("\n\n");
        String sseMessage = sb.toString();
        Log.debug(String.format("SSE broadcast: %s", eventType));
        processor.onNext(sseMessage);
    }

    public void broadcastConnected(boolean connected) {
        broadcast("FUSION_STATUS", Map.of("connected", connected));
    }

    public Multi<String> getEventStream() {
        return processor;
    }

    public void onConnection(Runnable listener) {
        connectionListeners.add(listener);
    }

    private void appendJson(StringBuilder sb, Map<String, Object> data) {
        sb.append("{");
        boolean first = true;
        for (Map.Entry<String, Object> entry : data.entrySet()) {
            if (!first) sb.append(",");
            first = false;
            sb.append("\"").append(entry.getKey()).append("\":");
            Object value = entry.getValue();
            if (value instanceof String) {
                sb.append("\"").append(value).append("\"");
            } else if (value instanceof Number || value instanceof Boolean) {
                sb.append(value);
            } else {
                sb.append("\"").append(value).append("\"");
            }
        }
        sb.append("}");
    }
}
