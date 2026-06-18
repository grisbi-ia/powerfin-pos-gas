package com.powerfin.pos.bridge.health;

import java.util.LinkedHashMap;
import java.util.Map;

import com.powerfin.pos.bridge.fusion.FusionTcpClient;
import com.powerfin.pos.bridge.print.PrinterConfig;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/health")
@Produces(MediaType.APPLICATION_JSON)
public class BridgeHealthResource {

    private final FusionTcpClient tcpClient;
    private final PrinterConfig printerConfig;

    public BridgeHealthResource(FusionTcpClient tcpClient,
                                 PrinterConfig printerConfig) {
        this.tcpClient = tcpClient;
        this.printerConfig = printerConfig;
    }

    @GET
    public Response health() {
        boolean fusionConnected = tcpClient.isConnected();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("status", fusionConnected ? "UP" : "DEGRADED");
        result.put("fusionConnected", fusionConnected);
        result.put("service", "FusionBridge");
        result.put("version", "0.19.5");
        result.put("printerPolicy", printerConfig.getPolicy().name());

        Map<String, Object> dependencies = new LinkedHashMap<>();
        dependencies.put("fusion", Map.of(
            "connected", fusionConnected,
            "ip", tcpClient.getFusionIp()
        ));
        // Printer IPs come from the database via the POS — not configured here
        dependencies.put("printer", Map.of(
            "note", "Printer IP configured in database (dispensers table)"
        ));
        result.put("dependencies", dependencies);

        int statusCode = fusionConnected ? 200 : 503;
        return Response.status(statusCode).entity(result).build();
    }
}
