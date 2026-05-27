package com.powerfin.pos.bridge.health;

import java.util.LinkedHashMap;
import java.util.Map;

import com.powerfin.pos.bridge.fusion.FusionTcpClient;
import com.powerfin.pos.bridge.print.PrinterConfig;
import com.powerfin.pos.bridge.print.PrinterConfig.IslandConfig;
import com.powerfin.pos.bridge.print.ReceiptBuilder;

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
    private final ReceiptBuilder receiptBuilder;

    public BridgeHealthResource(FusionTcpClient tcpClient,
                                 PrinterConfig printerConfig,
                                 ReceiptBuilder receiptBuilder) {
        this.tcpClient = tcpClient;
        this.printerConfig = printerConfig;
        this.receiptBuilder = receiptBuilder;
    }

    @GET
    public Response health() {
        boolean fusionConnected = tcpClient.isConnected();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("status", fusionConnected ? "UP" : "DEGRADED");
        result.put("fusionConnected", fusionConnected);
        result.put("service", "FusionBridge");
        result.put("version", "0.1.0-SNAPSHOT");
        result.put("printerPolicy", printerConfig.getPolicy().name());

        // Dynamic: iterate over all configured islands
        Map<String, Object> printers = new LinkedHashMap<>();
        for (var entry : printerConfig.getIslands().entrySet()) {
            IslandConfig cfg = entry.getValue();
            printers.put("island" + entry.getKey(), Map.of(
                    "ip", cfg.ip,
                    "reachable", receiptBuilder.isPrinterReachable(cfg.ip, cfg.port)
            ));
        }

        Map<String, Object> dependencies = new LinkedHashMap<>();
        dependencies.put("fusion", Map.of(
            "connected", fusionConnected,
            "ip", tcpClient.getFusionIp()
        ));
        dependencies.put("printers", printers);
        result.put("dependencies", dependencies);

        int statusCode = fusionConnected ? 200 : 503;
        return Response.status(statusCode).entity(result).build();
    }
}
