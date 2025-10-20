package com.aletheia.testservice.controller;

import com.aletheia.testservice.exception.*;
import com.aletheia.testservice.model.ErrorResponse;
import com.aletheia.testservice.model.ServiceInfo;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.sql.SQLException;
import java.time.Duration;
import java.time.Instant;
import java.util.*;

@RestController
@RequestMapping("/api/v1")
public class ErrorController {

    private static final Logger logger = LoggerFactory.getLogger(ErrorController.class);
    private final ObjectMapper objectMapper;
    private final Counter errorCountTotal;
    private final Counter exceptionThrownTotal;
    private final Instant startTime;

    public ErrorController(MeterRegistry meterRegistry, ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
        this.startTime = Instant.now();
        this.errorCountTotal = Counter.builder("error_count_total")
                .description("Total number of errors by type")
                .tag("service", "java-test-service")
                .register(meterRegistry);
        this.exceptionThrownTotal = Counter.builder("exception_thrown_total")
                .description("Total number of thrown exceptions by class")
                .tag("service", "java-test-service")
                .register(meterRegistry);
    }

    @GetMapping("/")
    public ResponseEntity<ServiceInfo> getServiceInfo() {
        ServiceInfo info = new ServiceInfo(
                "aletheia-java-test-service",
                "1.0.0",
                Duration.between(startTime, Instant.now()).toString(),
                true,
                Arrays.asList(
                        "GET /api/v1/",
                        "GET /api/v1/error?type={npe|array_index|divide_by_zero|json_error|sql_error|oom}",
                        "GET /actuator/health",
                        "GET /actuator/health/liveness",
                        "GET /actuator/health/readiness",
                        "GET /actuator/prometheus"
                )
        );
        return ResponseEntity.ok(info);
    }

    @GetMapping("/error")
    public ResponseEntity<Map<String, Object>> triggerError(
            @RequestParam(value = "type", defaultValue = "npe") String errorType) {

        String requestId = MDC.get("request_id");
        logger.warn("Triggering intentional error: {} (request_id={})", errorType, requestId);

        // Increment metrics
        errorCountTotal.increment();
        
        try {
            switch (errorType.toLowerCase()) {
                case "npe":
                case "null_pointer":
                    throwNullPointerException();
                    break;
                case "array_index":
                case "index_out_of_bounds":
                    throwArrayIndexOutOfBoundsException();
                    break;
                case "divide_by_zero":
                case "arithmetic":
                    throwArithmeticException();
                    break;
                case "json_error":
                case "json_processing":
                    throwJsonProcessingException();
                    break;
                case "sql_error":
                case "sql":
                    throwSQLException();
                    break;
                case "oom":
                case "out_of_memory":
                    throwOutOfMemoryError();
                    break;
                default:
                    return ResponseEntity.badRequest().body(Map.of(
                            "error", "Unknown error type: " + errorType,
                            "error_type", "invalid_request",
                            "timestamp", Instant.now().toString(),
                            "request_id", requestId,
                            "available_types", Arrays.asList("npe", "array_index", "divide_by_zero", "json_error", "sql_error", "oom")
                    ));
            }
        } catch (Exception e) {
            exceptionThrownTotal.increment();
            // Re-throw to let global exception handler handle it
            throw new RuntimeException(e);
        }

        // Should never reach here
        return ResponseEntity.ok().build();
    }

    private void throwNullPointerException() {
        logger.error("About to trigger NullPointerException");
        String str = null;
        str.length(); // This will throw NullPointerException
    }

    private void throwArrayIndexOutOfBoundsException() {
        logger.error("About to trigger ArrayIndexOutOfBoundsException");
        int[] array = {1, 2, 3};
        int value = array[10]; // This will throw ArrayIndexOutOfBoundsException
    }

    private void throwArithmeticException() {
        logger.error("About to trigger ArithmeticException");
        int x = 42;
        int y = 0;
        int result = x / y; // This will throw ArithmeticException
    }

    private void throwJsonProcessingException() throws Exception {
        logger.error("About to trigger JsonProcessingException");
        String invalidJson = "{\"broken\": json}";
        objectMapper.readValue(invalidJson, Map.class); // This will throw JsonProcessingException
    }

    private void throwSQLException() throws SQLException {
        logger.error("About to trigger SQLException");
        // Simulate database connection timeout
        try {
            Thread.sleep(100); // Simulate delay
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        throw new SQLException("Connection timeout after 30s", "08001", 0);
    }

    private void throwOutOfMemoryError() {
        logger.error("About to trigger OutOfMemoryError (simulated)");
        // Simulate OOM by allocating large array
        // NOTE: This may actually cause OOM in small containers
        List<byte[]> memoryHog = new ArrayList<>();
        try {
            while (true) {
                memoryHog.add(new byte[1024 * 1024 * 10]); // 10MB chunks
            }
        } catch (OutOfMemoryError e) {
            logger.error("OutOfMemoryError triggered", e);
            throw e;
        }
    }
}
