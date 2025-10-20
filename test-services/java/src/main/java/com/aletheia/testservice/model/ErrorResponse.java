package com.aletheia.testservice.model;

import java.time.Instant;

public record ErrorResponse(
        String error,
        String errorType,
        String exceptionClass,
        String timestamp,
        String requestId,
        StackTraceElement[] stackTrace
) {
    public ErrorResponse(String error, String errorType, String exceptionClass, String requestId, StackTraceElement[] stackTrace) {
        this(error, errorType, exceptionClass, Instant.now().toString(), requestId, stackTrace);
    }
}
