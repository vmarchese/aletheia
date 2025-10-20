# Aletheia Java Test Service

A Spring Boot service that intentionally generates various types of Java exceptions for testing Aletheia's troubleshooting capabilities.

## Features

- **Multiple Error Types**: NullPointerException, ArrayIndexOutOfBoundsException, ArithmeticException, JsonProcessingException, SQLException, OutOfMemoryError
- **OpenMetrics/Prometheus**: Full metrics exposure via `/actuator/prometheus`
- **Structured JSON Logging**: Using Logstash Logback encoder with MDC context
- **Health Probes**: Kubernetes-ready liveness and readiness probes
- **Configurable Failures**: Environment variables to trigger health probe failures
- **Complete Stack Traces**: All exceptions logged with full stack traces

## Prerequisites

- Java 21 or higher
- Maven 3.9 or higher
- Docker (for containerization)
- kubectl (for Kubernetes deployment)
- Local Kubernetes cluster (kind, k3d, minikube, or similar)

## Quick Start

### Build and Run Locally

```bash
# Build the application
make build

# Run locally
make run

# Or use Maven directly
mvn spring-boot:run
```

The service will start on port 8080.

### Build and Run with Docker

```bash
# Build Docker image
make docker-build

# Run container
make docker-run
```

### Deploy to Kubernetes

```bash
# Deploy to local cluster
make deploy

# Port-forward to access the service
kubectl port-forward -n aletheia-test svc/java-test-service 8080:80
```

## API Endpoints

### Service Information
```bash
curl http://localhost:8080/api/v1/
```

Returns service metadata and available endpoints.

### Error Endpoints

Trigger various error types:

```bash
# NullPointerException
curl "http://localhost:8080/api/v1/error?type=npe"

# ArrayIndexOutOfBoundsException
curl "http://localhost:8080/api/v1/error?type=array_index"

# ArithmeticException (divide by zero)
curl "http://localhost:8080/api/v1/error?type=divide_by_zero"

# JsonProcessingException
curl "http://localhost:8080/api/v1/error?type=json_error"

# SQLException (simulated database timeout)
curl "http://localhost:8080/api/v1/error?type=sql_error"

# OutOfMemoryError (WARNING: may crash the container)
curl "http://localhost:8080/api/v1/error?type=oom"
```

Or use the Makefile shortcuts:
```bash
make trigger-npe
make trigger-array-index
make trigger-divide-by-zero
make trigger-json-error
make trigger-sql-error
make trigger-oom
```

### Health and Metrics

```bash
# General health
curl http://localhost:8080/actuator/health

# Liveness probe
curl http://localhost:8080/actuator/health/liveness

# Readiness probe
curl http://localhost:8080/actuator/health/readiness

# Prometheus metrics
curl http://localhost:8080/actuator/prometheus
```

## Configuration

### Environment Variables

- `PORT`: HTTP port (default: 8080)
- `JAVA_OPTS`: JVM options
- `SPRING_PROFILES_ACTIVE`: Spring profile (default: production)
- `FAIL_LIVENESS_AFTER`: Duration after which liveness probe fails (e.g., "5m", "30s")
- `FAIL_READINESS_AFTER`: Duration after which readiness probe fails (e.g., "3m", "60s")

### Example: Trigger Health Probe Failures

```bash
# Run with failing probes
docker run -p 8080:8080 \
  -e FAIL_LIVENESS_AFTER=2m \
  -e FAIL_READINESS_AFTER=1m \
  aletheia/java-test-service:1.0.0
```

## Metrics

The service exposes the following custom metrics:

- `error_count_total{service,error_type}`: Total errors by type
- `exception_thrown_total{service,exception_class}`: Total exceptions by class
- `http_server_requests_seconds{method,uri,status}`: HTTP request timings
- `jvm_memory_used_bytes{area,id}`: JVM memory usage
- `jvm_gc_pause_seconds`: GC pause times

Plus all standard Spring Boot Actuator and JVM metrics.

## Logging

All logs are output in JSON format to stdout with the following fields:

- `timestamp`: ISO-8601 timestamp
- `level`: Log level (DEBUG, INFO, WARN, ERROR, FATAL)
- `logger`: Logger name
- `message`: Log message
- `thread`: Thread name
- `request_id`: Request correlation ID (from X-Request-Id header or generated)
- `exception`: Exception class name (if error)
- `stack_trace`: Full stack trace (if error)

### Example Log Entry

```json
{
  "timestamp": "2025-10-20T10:30:00.123Z",
  "level": "ERROR",
  "logger": "com.aletheia.testservice.exception.GlobalExceptionHandler",
  "message": "NullPointerException occurred (request_id=abc-123)",
  "thread": "http-nio-8080-exec-1",
  "request_id": "abc-123",
  "exception": "java.lang.NullPointerException",
  "stack_trace": "java.lang.NullPointerException: null\n\tat com.aletheia.testservice.controller.ErrorController.throwNullPointerException(ErrorController.java:95)\n..."
}
```

## Testing with Aletheia

This service is designed to validate Aletheia's troubleshooting capabilities.

### Example Scenario: NPE Investigation

1. Deploy the service to Kubernetes:
   ```bash
   make deploy
   ```

2. Trigger a burst of NullPointerExceptions:
   ```bash
   for i in {1..50}; do
     curl "http://localhost:8080/api/v1/error?type=npe" &
   done
   wait
   ```

3. Run Aletheia investigation:
   ```bash
   aletheia session open --name "java-npe-investigation"
   ```

4. Expected Aletheia behavior:
   - Collects logs with stack traces from Kubernetes
   - Identifies error spike in Prometheus metrics
   - Locates the exact file and line number causing the NPE
   - Provides diagnosis with confidence score
   - Recommends adding null checks

## Kubernetes Deployment Details

The service is deployed with:

- **Namespace**: `aletheia-test`
- **Replicas**: 2 (for availability testing)
- **Resources**:
  - Requests: 200m CPU, 256Mi memory
  - Limits: 500m CPU, 512Mi memory
- **Probes**:
  - Liveness: `/actuator/health/liveness` (30s initial, 10s period)
  - Readiness: `/actuator/health/readiness` (20s initial, 5s period)
- **ServiceMonitor**: Prometheus scraping enabled (15s interval)

## Troubleshooting

### Container Fails to Start

Check the logs:
```bash
make logs
```

Check health probes:
```bash
kubectl describe pod -n aletheia-test -l app=java-test-service
```

### OutOfMemoryError Crashes Container

The OOM error endpoint is designed to actually trigger OOM. This is intentional for testing. To recover:

```bash
# Delete the crashed pod
kubectl delete pod -n aletheia-test -l app=java-test-service

# Or restart the deployment
kubectl rollout restart deployment/java-test-service -n aletheia-test
```

### Metrics Not Showing in Prometheus

Verify ServiceMonitor is created:
```bash
kubectl get servicemonitor -n aletheia-test
```

Verify Prometheus is scraping:
```bash
kubectl logs -n monitoring -l app=prometheus
```

## Development

### Project Structure

```
java/
├── src/main/java/com/aletheia/testservice/
│   ├── AletheiaTestServiceApplication.java  # Main Spring Boot app
│   ├── config/
│   │   ├── ConfigurableHealthIndicator.java # Health probe logic
│   │   └── RequestIdFilter.java             # Request ID MDC filter
│   ├── controller/
│   │   └── ErrorController.java             # Error endpoint handlers
│   ├── exception/
│   │   └── GlobalExceptionHandler.java      # Exception handling
│   └── model/
│       ├── ErrorResponse.java               # Error response model
│       └── ServiceInfo.java                 # Service info model
├── src/main/resources/
│   ├── application.yml                      # Spring configuration
│   └── logback-spring.xml                   # Logging configuration
├── Dockerfile                               # Multi-stage Docker build
├── Makefile                                 # Build and deployment tasks
└── pom.xml                                  # Maven dependencies
```

### Adding New Error Types

1. Add error trigger method in `ErrorController.java`
2. Add case in `triggerError()` switch statement
3. Add exception handler in `GlobalExceptionHandler.java` (if new exception type)
4. Update Makefile with trigger command
5. Update README with new error type

## License

This is a test service for the Aletheia project. See main project for license details.
