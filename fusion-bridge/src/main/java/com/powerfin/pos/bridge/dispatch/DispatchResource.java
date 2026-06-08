package com.powerfin.pos.bridge.dispatch;

import java.util.Map;

import com.powerfin.pos.bridge.dispenser.DispenserStatusCache;
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

    @Inject
    DispenserStatusCache statusCache;

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

            // Clear any lingering STOP state before sending preset.
            // A previous STOP (manual or ATO) can leave the pump with "busy
            // buffers" that reject new PRESETs with TRANS_ERR_PRESET_STOPPED.
            String clearStopMsg = FusionMessageBuilder.buildClearStop(dispenserId);
            tcpClient.sendRaw(clearStopMsg);

            String message = FusionMessageBuilder.buildPreset(
                dispenserId, presetType, presetValue,
                hoseId, unitPrice, orderId,
                customerId, plate, priceList, paymentMethod
            );

            boolean sent = tcpClient.sendRaw(message);
            if (sent) {
                // Track active hose immediately so the frontend knows which hose
                // to paint the status on, even before the first status change arrives
                DispenserStatusCache.DispenserStatus existing = statusCache.get(dispenserId);
                if (existing != null) {
                    existing.setActiveHose(hoseId);
                    statusCache.update(existing);
                }

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

    /**
     * Manual Plan B — simple authorization with NO amount limit.
     * Only use when PRESET mode is confirmed unavailable (e.g. hardware issue).
     * The pump dispenses at console price with no automatic stop.
     * Requires explicit manual activation — never called automatically.
     */
    @POST
    @Path("/authorize-auth")
    public Response authorizeAuth(Map<String, Object> request) {
        if (!tcpClient.isConnected()) {
            return Response.status(503)
                .entity(Map.of("error", "No connection to Fusion"))
                .build();
        }

        try {
            int dispenserId = ((Number) request.getOrDefault("dispenser_id", 1)).intValue();
            int hoseId = ((Number) request.getOrDefault("hose_id", 1)).intValue();

            String message = FusionMessageBuilder.buildAuth(dispenserId, hoseId);

            boolean sent = tcpClient.sendRaw(message);
            if (sent) {
                Log.warnf("AUTH (manual Plan B) sent: pump=%d hose=%d",
                    dispenserId, hoseId);
                return Response.ok(Map.of(
                    "status", "AUTH_SENT",
                    "mode", "MANUAL_PLAN_B",
                    "warning", "Sin límite de monto. La bomba usa su precio de consola."
                )).build();
            } else {
                return Response.status(503)
                    .entity(Map.of("error", "Failed to send auth"))
                    .build();
            }
        } catch (Exception e) {
            Log.error("Error sending auth (Plan B)", e);
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

    /**
     * Stop an active dispensing operation (FUELLING state).
     * Sends REQ_PUMP_STOP to halt fuel flow, then schedules a delayed
     * CLEAR_STOP to finalize the transaction so the Wayne generates
     * NEW_TRANSACTION with the partial amount. Without CLEAR_STOP the
     * pump stays stuck in STOPPED with busy buffers, rejecting new PRESETs.
     */
    @POST
    @Path("/stop")
    public Response stop(Map<String, Object> request) {
        if (!tcpClient.isConnected()) {
            return Response.status(503)
                .entity(Map.of("error", "No connection to Fusion"))
                .build();
        }

        int dispenserId = ((Number) request.getOrDefault("dispenser_id", 1)).intValue();
        String message = FusionMessageBuilder.buildStop(dispenserId);
        boolean sent = tcpClient.sendRaw(message);

        if (sent) {
            Log.infof("Stop sent: dispenser %d", dispenserId);

            // Schedule delayed CLEAR_STOP so the Wayne finalizes the stopped
            // transaction and generates NEW_TRANSACTION for collection.
            // 2s delay lets the pump settle. Runs on virtual thread.
            Thread.startVirtualThread(() -> {
                try { Thread.sleep(2000); } catch (InterruptedException e) { return; }
                String clearMsg = FusionMessageBuilder.buildClearStop(dispenserId);
                tcpClient.sendRaw(clearMsg);
                Log.infof("Clear-stop sent: dispenser %d", dispenserId);
            });

            return Response.ok(Map.of("status", "STOPPED")).build();
        }
        return Response.status(503)
            .entity(Map.of("error", "Failed to stop"))
            .build();
    }

    /**
     * Lock a completed sale for payment processing.
     * Keeps the pump from returning to IDLE after dispensing.
     * Called automatically after NEW_TRANSACTION, but can also be called
     * manually if the auto-lock was missed.
     */
    @POST
    @Path("/payment-lock")
    public Response paymentLock(Map<String, Object> request) {
        if (!tcpClient.isConnected()) {
            return Response.status(503)
                .entity(Map.of("error", "No connection to Fusion"))
                .build();
        }

        try {
            String saleId = (String) request.getOrDefault("sale_id", "");
            String lockId = (String) request.getOrDefault("lock_id", saleId);

            String message = FusionMessageBuilder.buildLock(saleId, lockId);
            boolean sent = tcpClient.sendRaw(message);

            if (sent) {
                Log.infof("Payment lock sent: sale=%s lock=%s", saleId, lockId);
                return Response.ok(Map.of(
                    "status", "LOCKED",
                    "sale_id", saleId,
                    "lock_id", lockId
                )).build();
            }
            return Response.status(503)
                .entity(Map.of("error", "Failed to send lock"))
                .build();
        } catch (Exception e) {
            Log.error("Error locking sale for payment", e);
            return Response.serverError()
                .entity(Map.of("error", e.getMessage()))
                .build();
        }
    }

    /**
     * Clear/complete a locked sale after payment is collected.
     * Unlocks the pump so it returns to IDLE for the next customer.
     */
    @POST
    @Path("/payment-clear")
    public Response paymentClear(Map<String, Object> request) {
        if (!tcpClient.isConnected()) {
            return Response.status(503)
                .entity(Map.of("error", "No connection to Fusion"))
                .build();
        }

        try {
            String saleId = (String) request.getOrDefault("sale_id", "");
            String lockId = (String) request.getOrDefault("lock_id", saleId);
            String method = (String) request.getOrDefault("method", "CASH");

            String message = FusionMessageBuilder.buildClearSale(saleId, lockId, method);
            boolean sent = tcpClient.sendRaw(message);

            if (sent) {
                Log.infof("Payment clear sent: sale=%s method=%s", saleId, method);
                return Response.ok(Map.of(
                    "status", "CLEARED",
                    "sale_id", saleId
                )).build();
            }
            return Response.status(503)
                .entity(Map.of("error", "Failed to clear sale"))
                .build();
        } catch (Exception e) {
            Log.error("Error clearing sale", e);
            return Response.serverError()
                .entity(Map.of("error", e.getMessage()))
                .build();
        }
    }

    /**
     * Unlock a sale without clearing it (e.g. if payment needs to be postponed).
     * Returns the pump to IDLE.
     */
    @POST
    @Path("/payment-unlock")
    public Response paymentUnlock(Map<String, Object> request) {
        if (!tcpClient.isConnected()) {
            return Response.status(503)
                .entity(Map.of("error", "No connection to Fusion"))
                .build();
        }

        try {
            String saleId = (String) request.getOrDefault("sale_id", "");
            String lockId = (String) request.getOrDefault("lock_id", saleId);

            String message = FusionMessageBuilder.buildUnlock(saleId, lockId);
            boolean sent = tcpClient.sendRaw(message);

            if (sent) {
                Log.infof("Payment unlock sent: sale=%s", saleId);
                return Response.ok(Map.of(
                    "status", "UNLOCKED",
                    "sale_id", saleId
                )).build();
            }
            return Response.status(503)
                .entity(Map.of("error", "Failed to unlock sale"))
                .build();
        } catch (Exception e) {
            Log.error("Error unlocking sale", e);
            return Response.serverError()
                .entity(Map.of("error", e.getMessage()))
                .build();
        }
    }
}
