package com.powerfin.pos.bridge.dispenser;

import java.util.List;
import java.util.stream.Collectors;

import com.powerfin.pos.bridge.fusion.FusionTcpClient;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/dispensers")
@Produces(MediaType.APPLICATION_JSON)
public class DispenserResource {

    private final DispenserStatusCache cache;
    private final FusionTcpClient tcpClient;

    public DispenserResource(DispenserStatusCache cache, FusionTcpClient tcpClient) {
        this.cache = cache;
        this.tcpClient = tcpClient;
    }

    @GET
    public Response getAll() {
        List<DispenserStatusCache.DispenserStatus> dispensers = cache.getAll();
        List<java.util.Map<String, Object>> result = dispensers.stream()
            .map(d -> {
                java.util.Map<String, Object> map = new java.util.LinkedHashMap<>();
                map.put("dispenserId", d.getDispenserId());
                map.put("status", d.getStatus());
                map.put("subStatus", d.getSubStatus());
                map.put("hoseCount", d.getHoseCount());
                map.put("presetAmount", d.getPresetAmount());
                map.put("grade", d.getGrade());
                map.put("activeHose", d.getActiveHose());
                map.put("connected", d.isConnected());
                return map;
            })
            .collect(Collectors.toList());

        return Response.ok(java.util.Map.of(
            "dispensers", result,
            "fusionConnected", tcpClient.isConnected()
        )).build();
    }

    @GET
    @Path("/{id}")
    public Response getOne(@PathParam("id") int id) {
        DispenserStatusCache.DispenserStatus d = cache.get(id);
        if (d == null) {
            return Response.status(404)
                .entity(java.util.Map.of("error", "Dispenser not found: " + id))
                .build();
        }
        return Response.ok(java.util.Map.of(
            "dispenserId", d.getDispenserId(),
            "status", d.getStatus(),
            "subStatus", d.getSubStatus(),
            "hoseCount", d.getHoseCount(),
            "presetAmount", d.getPresetAmount(),
            "grade", d.getGrade(),
            "activeHose", d.getActiveHose(),
            "connected", d.isConnected()
        )).build();
    }
}
