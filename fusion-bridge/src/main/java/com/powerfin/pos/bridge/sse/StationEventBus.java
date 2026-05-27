package com.powerfin.pos.bridge.sse;

import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

import io.quarkus.logging.Log;
import io.smallrye.mutiny.Multi;
import io.smallrye.mutiny.operators.multi.processors.BroadcastProcessor;
import jakarta.enterprise.context.ApplicationScoped;

@ApplicationScoped
public class StationEventBus {

    /** Simple pair holding a named SSE event: eventType + JSON payload. */
    public record SseEvent(String eventType, String jsonData) {}

    private final BroadcastProcessor<SseEvent> processor = BroadcastProcessor.create();
    private final CopyOnWriteArrayList<Runnable> connectionListeners = new CopyOnWriteArrayList<>();

    public void broadcast(String eventType, Map<String, Object> data) {
        String json = toJson(data);
        Log.debug(String.format("SSE broadcast: %s → %s", eventType, json));
        processor.onNext(new SseEvent(eventType, json));
    }

    public void broadcastConnected(boolean connected) {
        broadcast("FUSION_STATUS", Map.of("connected", connected));
    }

    public Multi<SseEvent> getEventStream() {
        return processor;
    }

    public void onConnection(Runnable listener) {
        connectionListeners.add(listener);
    }

    private String toJson(Map<String, Object> data) {
        StringBuilder sb = new StringBuilder();
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
        return sb.toString();
    }
}
