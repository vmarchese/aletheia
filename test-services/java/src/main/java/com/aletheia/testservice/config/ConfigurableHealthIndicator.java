package com.aletheia.testservice.config;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;

@Component
public class ConfigurableHealthIndicator implements HealthIndicator {

    private final Instant startTime;
    private final Duration livenessFailAfter;
    private final Duration readinessFailAfter;

    public ConfigurableHealthIndicator() {
        this.startTime = Instant.now();
        
        // Read configuration from environment variables
        String livenessEnv = System.getenv("FAIL_LIVENESS_AFTER");
        this.livenessFailAfter = livenessEnv != null ? parseDuration(livenessEnv) : null;
        
        String readinessEnv = System.getenv("FAIL_READINESS_AFTER");
        this.readinessFailAfter = readinessEnv != null ? parseDuration(readinessEnv) : null;
    }

    @Override
    public Health health() {
        // This is the general health check (used for readiness by default)
        return checkReadiness();
    }

    public Health checkLiveness() {
        if (livenessFailAfter != null) {
            Duration uptime = Duration.between(startTime, Instant.now());
            if (uptime.compareTo(livenessFailAfter) >= 0) {
                return Health.down()
                        .withDetail("reason", "Liveness check failed (configured failure)")
                        .withDetail("uptime", uptime.toString())
                        .withDetail("fail_after", livenessFailAfter.toString())
                        .build();
            }
        }
        
        return Health.up().build();
    }

    public Health checkReadiness() {
        if (readinessFailAfter != null) {
            Duration uptime = Duration.between(startTime, Instant.now());
            if (uptime.compareTo(readinessFailAfter) >= 0) {
                return Health.down()
                        .withDetail("reason", "Readiness check failed (configured failure)")
                        .withDetail("uptime", uptime.toString())
                        .withDetail("fail_after", readinessFailAfter.toString())
                        .build();
            }
        }
        
        return Health.up().build();
    }

    private Duration parseDuration(String durationStr) {
        try {
            // Support formats like "30s", "1m", "5m30s", etc.
            if (durationStr.matches("\\d+s")) {
                return Duration.ofSeconds(Long.parseLong(durationStr.replace("s", "")));
            } else if (durationStr.matches("\\d+m")) {
                return Duration.ofMinutes(Long.parseLong(durationStr.replace("m", "")));
            } else {
                return Duration.parse("PT" + durationStr.toUpperCase());
            }
        } catch (Exception e) {
            return null;
        }
    }
}
