package com.powerfin.pos.bridge.dispatch;

import java.util.Map;

import com.powerfin.pos.bridge.fusion.FusionMessageBuilder;
import com.powerfin.pos.bridge.fusion.FusionTcpClient;

import io.quarkus.logging.Log;
import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/dispatch")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class DispatchResource {

    @Inject
    FusionTcpClient tcpClient;

    @POST
    @Path("/authorize")
    public Response authorize(Map<String, Object> request) {
        if (!tcpClient.isConnected()) {
            return Response.status(503)
                .entity(Map.of("error", "No connection to Fusion"))
                .build();
        }

        try {
            int dispenserId = ((Number) request.getOrDefault("dispenser_id", 1)).intValue();
            int hoseId = ((Number) request.getOrDefault("hose_id", 1)).intValue();
            String presetType = (String) request.getOrDefault("preset_type", "MONEY");
            String presetValue = (String) request.getOrDefault("preset_value", "0");
            double unitPrice = ((Number) request.getOrDefault("unit_price", 1.500)).doubleValue();
            String orderId = (String) request.getOrDefault("order_id", "");
            String customerId = (String) request.getOrDefault("customer_id", "");
            String plate = (String) request.getOrDefault("plate", "");
            String priceList = (String) request.getOrDefault("price_list", "STANDARD");
            String paymentMethod = (String) request.getOrDefault("payment_method", "EFECTIVO");

            String message = FusionMessageBuilder.buildPreset(
                dispenserId, presetType, presetValue,
                hoseId, unitPrice, orderId,
                customerId, plate, priceList, paymentMethod
            );

            boolean sent = tcpClient.sendRaw(message);
            if (sent) {
                Log.infof("Preset sent: pump=%d hose=%d order=%s value=%s",
                    dispenserId, hoseId, orderId, presetValue);
                return Response.ok(Map.of(
                    "status", "PRESET_SENT",
                    "order_id", orderId
                )).build();
            } else {
                return Response.status(503)
                    .entity(Map.of("error", "Failed to send preset"))
                    .build();
            }
        } catch (Exception e) {
            Log.error("Error authorizing dispatch", e);
            return Response.serverError()
                .entity(Map.of("error", e.getMessage()))
                .build();
        }
    }

    @POST
    @Path("/cancel")
    public Response cancel(Map<String, Object> request) {
        if (!tcpClient.isConnected()) {
            return Response.status(503)
                .entity(Map.of("error", "No connection to Fusion"))
                .build();
        }

        int dispenserId = ((Number) request.getOrDefault("dispenser_id", 1)).intValue();
        String message = FusionMessageBuilder.buildClearPreset(dispenserId);
        boolean sent = tcpClient.sendRaw(message);

        if (sent) {
            return Response.ok(Map.of("status", "CANCELLED")).build();
        }
        return Response.status(503)
            .entity(Map.of("error", "Failed to cancel"))
            .build();
    }
}
