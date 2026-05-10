package com.powerfin.pos.bridge.sse;

import com.powerfin.pos.bridge.fusion.FusionTcpClient;

import io.smallrye.mutiny.Multi;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

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
    public Multi<String> stream() {
        return Multi.createBy().merging()
            .streams(
                Multi.createFrom().item(buildInitialEvent()),
                eventBus.getEventStream()
            );
    }

    private String buildInitialEvent() {
        boolean connected = tcpClient.isConnected();
        return "event:INIT\ndata:{\"fusionConnected\":" + connected + "}\n\n";
    }
}
