package com.powerfin.pos.bridge.print;

import java.io.IOException;
import java.net.ConnectException;
import java.net.InetSocketAddress;
import java.net.Socket;

import io.quarkus.logging.Log;
import jakarta.enterprise.context.ApplicationScoped;

@ApplicationScoped
public class ThermalPrinter {

    private static final int SOCKET_TIMEOUT_MS = 5_000;

    /**
     * Sends raw bytes directly to the thermal printer via TCP socket.
     * No drivers, no CUPS — just a raw TCP connection to port 9100.
     */
    public void print(String printerIp, int printerPort, byte[] data) {
        Log.infof("Printing to %s:%d (%d bytes)", printerIp, printerPort, data.length);

        try (Socket socket = new Socket()) {
            socket.connect(
                new InetSocketAddress(printerIp, printerPort),
                SOCKET_TIMEOUT_MS
            );
            socket.setSoTimeout(SOCKET_TIMEOUT_MS);
            socket.getOutputStream().write(data);
            socket.getOutputStream().flush();
            Log.infof("Print sent successfully to %s", printerIp);

        } catch (ConnectException e) {
            Log.errorf("Printer %s:%d not reachable: %s", printerIp, printerPort, e.getMessage());
            throw new PrintException("Printer not reachable: " + printerIp + ":" + printerPort, e);

        } catch (IOException e) {
            Log.errorf("Print error to %s:%d: %s", printerIp, printerPort, e.getMessage());
            throw new PrintException("Print failed: " + e.getMessage(), e);
        }
    }
}
