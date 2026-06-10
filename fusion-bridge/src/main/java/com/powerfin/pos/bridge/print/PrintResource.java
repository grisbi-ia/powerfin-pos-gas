package com.powerfin.pos.bridge.print;

import java.util.Map;

import io.quarkus.logging.Log;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.PUT;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

/**
 * Print resource. Printer IPs come from the POS (read from the database).
 * FusionBridge has NO printer IP configuration — if the POS doesn't send
 * printerIp + printerPort, the request fails with a clear error.
 */
@Path("/api/print")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class PrintResource {

    private final PrinterConfig printerConfig;
    private final ReceiptBuilder receiptBuilder;
    private final ThermalPrinter thermalPrinter;
    private final TemplateRenderer templateRenderer;

    public PrintResource(PrinterConfig printerConfig,
                         ReceiptBuilder receiptBuilder,
                         ThermalPrinter thermalPrinter,
                         TemplateRenderer templateRenderer) {
        this.printerConfig = printerConfig;
        this.receiptBuilder = receiptBuilder;
        this.thermalPrinter = thermalPrinter;
        this.templateRenderer = templateRenderer;
    }

    // ── Print ────────────────────────────────────────────────

    @POST
    public Response print(Map<String, Object> request) {
        String type = (String) request.getOrDefault("type", "");
        boolean preview = Boolean.TRUE.equals(request.get("preview"));

        try {
            byte[] receiptBytes;

            if ("FUEL_RECEIPT".equals(type)) {
                ReceiptBuilder.FuelReceiptData data =
                        ReceiptBuilder.FuelReceiptData.fromMap(request);
                receiptBytes = receiptBuilder.buildFuelReceipt(data);

            } else if ("CASH_MOVEMENT".equals(type)) {
                ReceiptBuilder.CashMovementData data =
                        ReceiptBuilder.CashMovementData.fromMap(request);
                receiptBytes = receiptBuilder.buildCashMovementReceipt(data);

            } else {
                return Response.status(400)
                        .entity(Map.of("error", "Unknown receipt type: " + type))
                        .build();
            }

            // Preview mode: return rendered text (dev only, saves paper)
            if (preview) {
                String text = new String(receiptBytes, java.nio.charset.StandardCharsets.UTF_8);
                return Response.ok(Map.of(
                        "status", "PREVIEW",
                        "preview", text
                )).build();
            }

            // Printer IP MUST come from the POS (read from database).
            // FusionBridge has no printer IP configuration.
            String printerIp = strParam(request, "printerIp");
            int printerPort = intParam(request, "printerPort", 0);

            if (printerIp == null || printerIp.isEmpty()) {
                return Response.status(400).entity(Map.of(
                        "error", "printerIp es requerido — configure printer_ip en la tabla dispensers"
                )).build();
            }
            if (printerPort == 0) {
                printerPort = 9100;
            }

            thermalPrinter.print(printerIp, printerPort, receiptBytes);

            return Response.ok(Map.of(
                    "status", "PRINTED",
                    "printer_ip", printerIp
            )).build();

        } catch (PrintException e) {
            Log.errorf("Print error: %s", e.getMessage());
            return Response.status(503)
                    .entity(Map.of("error", e.getMessage()))
                    .build();

        } catch (Exception e) {
            Log.error("Internal print error", e);
            return Response.status(500)
                    .entity(Map.of("error", "Internal error"))
                    .build();
        }
    }

    // ── Test print (requires explicit printer IP) ────────────

    @POST
    @Path("/test")
    public Response testPrint(Map<String, Object> body) {
        String printerIp = strParam(body, "printerIp");

        if (printerIp == null || printerIp.isEmpty()) {
            return Response.status(400).entity(Map.of(
                    "error", "printerIp es requerido para test de impresión"
            )).build();
        }
        int printerPort = intParam(body, "printerPort", 9100);

        try {
            String now = java.time.LocalDateTime.now()
                    .format(java.time.format.DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm"));

            byte[] testTicket = buildTestTicket(printerIp, now);

            thermalPrinter.print(printerIp, printerPort, testTicket);

            return Response.ok(Map.of(
                    "status", "PRINTED",
                    "printer_ip", printerIp
            )).build();

        } catch (PrintException e) {
            return Response.status(503)
                    .entity(Map.of("error", e.getMessage()))
                    .build();
        } catch (Exception e) {
            Log.error("Test print error", e);
            return Response.status(500)
                    .entity(Map.of("error", "Internal error"))
                    .build();
        }
    }

    /** Builds a simple test ticket in raw ESC/POS bytes. */
    private byte[] buildTestTicket(String printerIp, String dateTime) {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        try {
            byte[] boldOn  = { 0x1B, '!', 0x08 };
            byte[] boldOff = { 0x1B, '!', 0x00 };
            byte[] center  = { 0x1B, 'a', 0x01 };
            byte[] left    = { 0x1B, 'a', 0x00 };
            byte[] lf      = { '\n' };
            byte[] cut     = { 0x1D, 'V', 0x00 };

            String dashes = "=".repeat(40);

            out.write(lf);
            out.write(center);
            out.write(boldOn);
            out.write(dashes.getBytes()); out.write(lf);
            out.write("    PRUEBA DE IMPRESORA".getBytes()); out.write(lf);
            out.write(("    " + printerIp + " — " + dateTime).getBytes()); out.write(lf);
            out.write(dashes.getBytes()); out.write(lf);
            out.write(boldOff);
            out.write(left);
            out.write(lf);
            out.write("Si puede leer este ticket,".getBytes()); out.write(lf);
            out.write("la impresora funciona correctamente.".getBytes()); out.write(lf);
            out.write(lf);
            out.write(center);
            out.write(dashes.getBytes()); out.write(lf);
            out.write(left);
            out.write(lf); out.write(lf);
            out.write(cut);
        } catch (java.io.IOException ignored) { }
        return out.toByteArray();
    }

    // ── Policy ───────────────────────────────────────────────

    @GET
    @Path("/policy")
    public Response getPolicy() {
        return Response.ok(Map.of(
                "policy", printerConfig.getPolicy().name()
        )).build();
    }

    // ── Receipt template ─────────────────────────────────────

    @GET
    @Path("/template")
    public Response getTemplate() {
        return Response.ok(Map.of(
                "template", templateRenderer.getTemplate()
        )).build();
    }

    @PUT
    @Path("/template")
    public Response updateTemplate(Map<String, Object> body) {
        String newTemplate = (String) body.get("template");
        if (newTemplate == null || newTemplate.isBlank()) {
            return Response.status(400)
                    .entity(Map.of("error", "Missing 'template' field"))
                    .build();
        }
        try {
            templateRenderer.saveTemplate(newTemplate);
            return Response.ok(Map.of("status", "UPDATED")).build();
        } catch (Exception e) {
            Log.error("Failed to save template", e);
            return Response.status(500)
                    .entity(Map.of("error", e.getMessage()))
                    .build();
        }
    }

    // ── Helpers ──────────────────────────────────────────────

    private static String strParam(Map<String, Object> map, String key) {
        Object v = map.get(key);
        return v != null ? v.toString() : null;
    }

    private static int intParam(Map<String, Object> map, String key, int defaultVal) {
        Object v = map.get(key);
        if (v instanceof Number n) return n.intValue();
        if (v instanceof String s) {
            try { return Integer.parseInt(s); } catch (NumberFormatException e) { }
        }
        return defaultVal;
    }
}
