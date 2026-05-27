package com.powerfin.pos.bridge.print;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.eclipse.microprofile.config.inject.ConfigProperty;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import io.quarkus.logging.Log;
import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
public class PrinterConfig {

    public enum Policy { ALWAYS, ASK, NEVER }

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final Path configFile;
    private final Map<Integer, IslandConfig> islands = new ConcurrentHashMap<>();
    private volatile Policy policy;

    // ── Constructor: initial defaults from application.properties ──

    @Inject
    public PrinterConfig(
            @ConfigProperty(name = "printer.policy", defaultValue = "ASK")
            String policyStr,
            @ConfigProperty(name = "printer.config.file",
                defaultValue = "/var/lib/powerfin/pos/printer-config.json")
            String configFilePath) {
        this.configFile = Paths.get(configFilePath);
        this.policy = parsePolicy(policyStr);
    }

    // ── Init: load JSON file, fall back to per-island properties ──

    @PostConstruct
    void init() {
        if (Files.exists(configFile)) {
            try {
                loadFromFile();
                Log.infof("Printer config loaded from %s: %d island(s), policy=%s",
                        configFile, islands.size(), policy);
                return;
            } catch (IOException e) {
                Log.warnf("Failed to load %s, using defaults: %s",
                        configFile, e.getMessage());
            }
        }

        // No JSON file — seed islands from individual properties (backward compat)
        String island1Ip = getProperty("printer.island1.ip", "192.168.1.31");
        int island1Port = getIntProperty("printer.island1.port", 9100);
        String island2Ip = getProperty("printer.island2.ip", "192.168.1.32");
        int island2Port = getIntProperty("printer.island2.port", 9100);

        islands.put(1, new IslandConfig(island1Ip, island1Port));
        islands.put(2, new IslandConfig(island2Ip, island2Port));

        Log.infof("Printer config seeded from properties: %d island(s), policy=%s",
                islands.size(), policy);
    }

    // ── Runtime config file load / save ──────────────────────

    @SuppressWarnings("unchecked")
    private void loadFromFile() throws IOException {
        Map<String, Object> root = MAPPER.readValue(
                configFile.toFile(),
                new TypeReference<Map<String, Object>>() {});

        if (root.containsKey("policy")) {
            this.policy = parsePolicy(root.get("policy").toString());
        }

        Map<String, Object> islandMap = (Map<String, Object>) root.get("islands");
        if (islandMap != null) {
            islands.clear();
            for (var entry : islandMap.entrySet()) {
                int num = Integer.parseInt(entry.getKey());
                Map<String, Object> cfg = (Map<String, Object>) entry.getValue();
                String ip = cfg.getOrDefault("ip", "192.168.1.31").toString();
                int port = ((Number) cfg.getOrDefault("port", 9100)).intValue();
                islands.put(num, new IslandConfig(ip, port));
            }
        }
    }

    private void saveToFile() {
        try {
            Files.createDirectories(configFile.getParent());

            Map<String, Object> root = new LinkedHashMap<>();
            root.put("policy", policy.name());

            Map<String, Object> islandMap = new LinkedHashMap<>();
            for (var entry : islands.entrySet()) {
                islandMap.put(entry.getKey().toString(), Map.of(
                        "ip", entry.getValue().ip,
                        "port", entry.getValue().port
                ));
            }
            root.put("islands", islandMap);

            MAPPER.writerWithDefaultPrettyPrinter()
                    .writeValue(configFile.toFile(), root);

            Log.infof("Printer config saved to %s", configFile);
        } catch (IOException e) {
            Log.errorf("Failed to save printer config: %s", e.getMessage());
        }
    }

    // ── Public API ──────────────────────────────────────────

    public Policy getPolicy() {
        return policy;
    }

    /** Returns the IP for a given island number. */
    public String getIp(int island) {
        IslandConfig cfg = islands.get(island);
        return cfg != null ? cfg.ip : "192.168.1.31";
    }

    /** Returns the port for a given island number. */
    public int getPort(int island) {
        IslandConfig cfg = islands.get(island);
        return cfg != null ? cfg.port : 9100;
    }

    /** Returns an unmodifiable snapshot of all islands. */
    public Map<Integer, IslandConfig> getIslands() {
        return Collections.unmodifiableMap(new LinkedHashMap<>(islands));
    }

    /**
     * Updates config from an external map (e.g. PUT /api/print/config).
     * Merges: only replaces fields that are present.
     * Persists to JSON file on success.
     */
    @SuppressWarnings("unchecked")
    public void updateFromMap(Map<String, Object> data) {
        if (data.containsKey("policy")) {
            this.policy = parsePolicy(data.get("policy").toString());
        }

        Map<String, Object> islandMap = (Map<String, Object>) data.get("islands");
        if (islandMap != null) {
            for (var entry : islandMap.entrySet()) {
                int num = Integer.parseInt(entry.getKey());
                Map<String, Object> cfg = (Map<String, Object>) entry.getValue();
                if (cfg.containsKey("ip") || cfg.containsKey("port")) {
                    IslandConfig existing = islands.getOrDefault(num,
                            new IslandConfig("192.168.1.31", 9100));
                    String ip = cfg.containsKey("ip")
                            ? cfg.get("ip").toString() : existing.ip;
                    int port = cfg.containsKey("port")
                            ? ((Number) cfg.get("port")).intValue() : existing.port;
                    islands.put(num, new IslandConfig(ip, port));
                }
            }
        }

        saveToFile();
    }

    // ── Backward-compat helpers (used by health, old code) ──

    /** @deprecated use getIp(1) */
    public String getIsland1Ip() { return getIp(1); }
    /** @deprecated use getPort(1) */
    public int getIsland1Port() { return getPort(1); }
    /** @deprecated use getIp(2) */
    public String getIsland2Ip() { return getIp(2); }
    /** @deprecated use getPort(2) */
    public int getIsland2Port() { return getPort(2); }

    /** @deprecated use island-based lookup */
    public String getPrinterIp(int dispenserId) {
        return getIp(dispenserId <= 2 ? 1 : 2);
    }
    /** @deprecated use island-based lookup */
    public int getPrinterPort(int dispenserId) {
        return getPort(dispenserId <= 2 ? 1 : 2);
    }

    // ── Internal ────────────────────────────────────────────

    private static Policy parsePolicy(String s) {
        try { return Policy.valueOf(s.toUpperCase()); }
        catch (IllegalArgumentException e) { return Policy.ASK; }
    }

    private static String getProperty(String name, String def) {
        String v = System.getProperty(name);
        if (v != null) return v;
        v = System.getenv(nameToEnv(name));
        return v != null ? v : def;
    }

    private static int getIntProperty(String name, int def) {
        try { return Integer.parseInt(getProperty(name, String.valueOf(def))); }
        catch (NumberFormatException e) { return def; }
    }

    private static String nameToEnv(String name) {
        return name.replace('.', '_').toUpperCase();
    }

    // ── Value class ─────────────────────────────────────────

    public static class IslandConfig {
        public final String ip;
        public final int port;

        public IslandConfig(String ip, int port) {
            this.ip = ip;
            this.port = port;
        }

        @Override
        public String toString() {
            return ip + ":" + port;
        }
    }
}
