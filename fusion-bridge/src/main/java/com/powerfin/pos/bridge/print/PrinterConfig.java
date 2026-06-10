package com.powerfin.pos.bridge.print;

import java.util.Map;

import org.eclipse.microprofile.config.inject.ConfigProperty;

import io.quarkus.logging.Log;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

/**
 * Printer policy only. Printer IPs come from the database via the POS —
 * FusionBridge has NO printer IP configuration of its own.
 */
@ApplicationScoped
public class PrinterConfig {

    public enum Policy { ALWAYS, ASK, NEVER }

    private volatile Policy policy;

    @Inject
    public PrinterConfig(
            @ConfigProperty(name = "printer.policy", defaultValue = "ASK")
            String policyStr) {
        this.policy = parsePolicy(policyStr);
    }

    // ── Public API ──────────────────────────────────────────

    public Policy getPolicy() {
        return policy;
    }

    public void updatePolicy(String policyStr) {
        this.policy = parsePolicy(policyStr);
        Log.infof("Printer policy updated: %s", policy);
    }

    // ── Internal ────────────────────────────────────────────

    private static Policy parsePolicy(String s) {
        try { return Policy.valueOf(s.toUpperCase()); }
        catch (IllegalArgumentException e) { return Policy.ASK; }
    }
}
