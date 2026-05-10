package com.powerfin.pos.bridge.health;

import java.util.LinkedHashMap;
import java.util.Map;

import com.powerfin.pos.bridge.fusion.FusionTcpClient;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/health")
@Produces(MediaType.APPLICATION_JSON)
public class BridgeHealthResource {

    private final FusionTcpClient tcpClient;

    public BridgeHealthResource(FusionTcpClient tcpClient) {
        this.tcpClient = tcpClient;
    }

    @GET
    public Response health() {
        boolean fusionConnected = tcpClient.isConnected();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("status", fusionConnected ? "UP" : "DEGRADED");
        result.put("fusionConnected", fusionConnected);
        result.put("service", "FusionBridge");
        result.put("version", "0.1.0-SNAPSHOT");

        Map<String, Object> dependencies = new LinkedHashMap<>();
        dependencies.put(            "fusion", Map.of(
            "connected", fusionConnected,
            "ip", tcpClient.getFusionIp()
        ));
        result.put("dependencies", dependencies);

        int statusCode = fusionConnected ? 200 : 503;
        return Response.status(statusCode).entity(result).build();
    }
}
