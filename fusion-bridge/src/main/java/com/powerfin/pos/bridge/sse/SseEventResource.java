package com.powerfin.pos.bridge.sse;

import com.powerfin.pos.bridge.fusion.FusionTcpClient;

import io.quarkus.logging.Log;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.sse.Sse;
import jakarta.ws.rs.sse.SseEventSink;

@Path("/api/events")
public class SseEventResource {

    private final StationEventBus eventBus;
    private final FusionTcpClient tcpClient;

    public SseEventResource(StationEventBus eventBus, FusionTcpClient tcpClient) {
        this.eventBus = eventBus;
        this.tcpClient = tcpClient;
    }

    @GET
    @Produces(MediaType.SERVER_SENT_EVENTS)
    public void stream(@Context SseEventSink sink, @Context Sse sse) {
        if (sink == null || sse == null) return;

        // Send initial connection status
        boolean connected = tcpClient.isConnected();
        sink.send(sse.newEventBuilder()
            .name("INIT")
            .data("{\"fusionConnected\":" + connected + "}")
            .build());

        // Subscribe to event bus and bridge to SSE sink
        eventBus.getEventStream().subscribe().with(
            event -> {
                if (!sink.isClosed()) {
                    sink.send(sse.newEventBuilder()
                        .name(event.eventType())
                        .data(event.jsonData())
                        .build());
                }
            },
            failure -> {
                Log.error("SSE stream error", failure);
            }
        );
    }
}
