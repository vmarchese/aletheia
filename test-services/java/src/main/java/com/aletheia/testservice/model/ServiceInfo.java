package com.aletheia.testservice.model;

import java.util.List;

public record ServiceInfo(
        String service,
        String version,
        String uptime,
        Boolean ready,
        List<String> endpoints
) {
}
