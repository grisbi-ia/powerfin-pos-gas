package com.powerfin.pos.bridge.recovery;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import com.powerfin.pos.bridge.fusion.FusionTcpClient;

import io.quarkus.logging.Log;
import io.vertx.core.Vertx;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

/**
 * Recovers dispatches that completed while the TCP connection to the Wayne
 * Synergy was down.
 *
 * <p>On reconnect, FusionBridge requests pump status from the Wayne.
 * If a pump reports {@code PAY_AL=ON} (unpaid sale alarm), that means fuel
 * was dispensed but the sale was never collected — typically because the
 * NEW_TRANSACTION event was lost during the disconnect window.</p>
 *
 * <p>RecoveryService queries the Wayne's last 5 sales for that pump via
 * {@code REQ_GET_PUMP_SALES}. The Wayne responds with standard
 * {@code EVT_PUMP_NEW_TRANSACTION} events, which flow through the normal
 * {@code FusionEventHandler} pipeline: completeDispatchOnBackend is called
 * with the actual amounts, and the POS learns about the completed dispatch
 * via its periodic reconciliation with the backend (every 3s).</p>
 *
 * <p>No new message parsing is needed — we reuse the existing handler.</p>
 */
@ApplicationScoped
public class RecoveryService {

    @Inject
    Vertx vertx;

    private FusionTcpClient tcpClient;
    private final Map<Integer, Boolean> pumpPayAlarms = new ConcurrentHashMap<>();
    private boolean reconnectPending = false;
    private boolean firstConnection = true;

    /**
     * Called by FusionTcpClient after construction to provide itself.
     * Setter injection avoids a circular @Inject dependency.
     */
    public void setTcpClient(FusionTcpClient client) {
        this.tcpClient = client;
    }

    /**
     * Called by FusionEventHandler every time a pump status arrives.
     * Records whether the pump has an unpaid sale alarm.
     */
    public void onPumpStatus(int pumpId, boolean payAlarm) {
        pumpPayAlarms.put(pumpId, payAlarm);
        if (payAlarm) {
            Log.debugf("[Recovery] Pump %d PAY_AL=ON recorded", pumpId);
        }
    }

    /**
     * Called by FusionTcpClient after the reconnection sequence
     * (subscriptions + REQ_PUMP_STATUS_ID_000 sent).
     *
     * <p>Schedules a delayed check so the Wayne has time to respond
     * with pump statuses before we inspect PAY_AL state.</p>
     */
    public void onReconnect() {
        if (firstConnection) {
            firstConnection = false;
            Log.debug("[Recovery] First connection — skipping recovery check");
            return;
        }

        reconnectPending = true;
        pumpPayAlarms.clear();

        // Wait for the Wayne to respond with EVT_PUMP_STATUS_CHANGE for
        // each pump. 4 seconds is ample — in practice the Wayne responds
        // in under 1 second for a 4-pump site.
        vertx.setTimer(4_000, id -> recoverIfNeeded());
    }

    private void recoverIfNeeded() {
        if (!reconnectPending) return;
        reconnectPending = false;

        if (tcpClient == null || !tcpClient.isConnected()) {
            Log.debug("[Recovery] Not connected — skipping recovery");
            return;
        }

        boolean anyAlarm = false;
        for (Map.Entry<Integer, Boolean> entry : pumpPayAlarms.entrySet()) {
            if (entry.getValue()) {
                int pumpId = entry.getKey();
                Log.warnf("[Recovery] Pump %d has PAY_ALARM (unpaid sale) — "
                    + "querying last 5 sales from Wayne for recovery", pumpId);
                boolean sent = tcpClient.sendMessage("REQ_GET_PUMP_SALES",
                    "PM=" + pumpId + "|QT=5", "Forecourt", "");
                if (sent) {
                    anyAlarm = true;
                    Log.infof("[Recovery] REQ_GET_PUMP_SALES sent for pump %d — "
                        + "waiting for EVT_PUMP_NEW_TRANSACTION responses", pumpId);
                } else {
                    Log.errorf("[Recovery] Failed to send REQ_GET_PUMP_SALES for pump %d "
                        + "— socket not connected", pumpId);
                }
            }
        }

        if (!anyAlarm) {
            Log.debug("[Recovery] No PAY_ALARMs detected — nothing to recover");
        }
    }
}
