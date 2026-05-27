package com.powerfin.pos.bridge.print;

public class PrintException extends RuntimeException {

    public PrintException(String message) {
        super(message);
    }

    public PrintException(String message, Throwable cause) {
        super(message, cause);
    }
}
