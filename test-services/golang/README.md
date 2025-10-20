# Aletheia Golang Error Test Service

A test service written in Go that intentionally generates errors for validating Aletheia's troubleshooting capabilities.

## Features

- **Multiple Error Types**: Trigger different kinds of errors (nil pointer, index out of bounds, divide by zero, JSON errors, DB timeouts)
- **Structured JSON Logging**: All logs in JSON format with timestamps, request IDs, and complete stack traces
- **Prometheus Metrics**: OpenMetrics-compatible `/metrics` endpoint with custom error metrics
- **Health Probes**: Kubernetes-compatible liveness and readiness probes
- **Configurable Failures**: Test probe failures via environment variables

## API Endpoints

### Main Endpoints

- `GET /` - Service information and available endpoints
- `GET /api/v1/error?type={error_type}` - Trigger intentional errors
- `GET /healthz` - Liveness probe
- `GET /readyz` - Readiness probe
- `GET /metrics` - Prometheus metrics (port 9090)

### Error Types

- `nil_pointer` - Causes a nil pointer dereference panic
- `index_out_of_bounds` - Causes an array index out of bounds panic
- `divide_by_zero` - Causes a division by zero panic
- `json_unmarshal` - Returns a JSON unmarshaling error
- `db_timeout` - Simulates a database connection timeout

## Configuration

Environment variables:

- `PORT` - HTTP server port (default: 8080)
- `METRICS_PORT` - Metrics server port (default: 9090)
- `STARTUP_DELAY` - Delay before marking service as ready (e.g., "10s")
- `FAIL_LIVENESS_AFTER` - Duration after which liveness probe fails (e.g., "5m")
- `FAIL_READINESS_AFTER` - Duration after which readiness probe fails (e.g., "3m")

## Metrics

Custom Prometheus metrics:

- `http_requests_total{endpoint, status}` - Counter of HTTP requests
- `http_request_duration_seconds{endpoint}` - Histogram of request durations
- `error_count_total{error_type}` - Counter of errors by type
- `panic_recovery_total` - Counter of recovered panics

Plus standard Go runtime metrics (heap, GC, goroutines, etc.)

## Log Format

All logs are JSON-formatted with the following fields:

```json
{
  "timestamp": "2025-10-20T10:30:00Z",
  "level": "ERROR",
  "message": "Panic recovered",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "client_ip": "10.0.0.1:54321",
  "method": "GET",
  "path": "/api/v1/error",
  "status": 500,
  "duration_ms": 42,
  "error": "runtime error: invalid memory address or nil pointer dereference",
  "error_type": "nil_pointer",
  "stack_trace": "goroutine 1 [running]:\nmain.errorHandler(...)\n\t/app/main.go:123"
}
```

## Building

### Local Build

```bash
cd test-services/golang
go mod download
go build -o main .
./main
```

### Docker Build

```bash
cd test-services/golang
docker build -t aletheia/golang-test-service:latest .
```

### For kind/k3d

```bash
# Build and load into kind
docker build -t aletheia/golang-test-service:latest .
kind load docker-image aletheia/golang-test-service:latest

# Or for k3d
k3d image import aletheia/golang-test-service:latest
```

## Deploying to Kubernetes

```bash
# Apply all manifests
kubectl apply -f test-services/k8s/golang/

# Verify deployment
kubectl -n aletheia-test get pods
kubectl -n aletheia-test get svc

# Check logs
kubectl -n aletheia-test logs -l app=golang-test-service --tail=50

# Port forward to test locally
kubectl -n aletheia-test port-forward svc/golang-test-service 8080:80 9090:9090
```

## Testing

### Trigger Errors

```bash
# Nil pointer error
curl http://localhost:8080/api/v1/error?type=nil_pointer

# Index out of bounds
curl http://localhost:8080/api/v1/error?type=index_out_of_bounds

# Divide by zero
curl http://localhost:8080/api/v1/error?type=divide_by_zero

# JSON unmarshal error
curl http://localhost:8080/api/v1/error?type=json_unmarshal

# Database timeout
curl http://localhost:8080/api/v1/error?type=db_timeout
```

### Check Metrics

```bash
curl http://localhost:9090/metrics
```

### Check Health

```bash
# Liveness
curl http://localhost:8080/healthz

# Readiness
curl http://localhost:8080/readyz
```

## Using with Aletheia

1. Deploy the service to Kubernetes
2. Trigger errors using the API
3. Start an Aletheia investigation:

```bash
aletheia session open --name "golang-error-test"
```

4. When prompted:
   - Problem description: "Golang test service is crashing with nil pointer errors"
   - Time window: Last 15 minutes
   - Data source: Kubernetes (select the aletheia-test namespace)
   - Pod: golang-test-service-*

Expected Aletheia output:
- Identifies error spike in metrics
- Collects logs with stack traces
- Correlates deployment timing
- Identifies file and line number in Go code
- Provides diagnosis with confidence >0.7

## Architecture

```
┌─────────────────────────────────────┐
│   Golang Test Service               │
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │ HTTP Server  │  │   Metrics   │ │
│  │   :8080      │  │   :9090     │ │
│  └──────────────┘  └─────────────┘ │
│         │                  │        │
│         ├─ /               │        │
│         ├─ /api/v1/error   │        │
│         ├─ /healthz        │        │
│         └─ /readyz          │        │
│                            │        │
│                       /metrics      │
│                            │        │
└────────────────────────────┼────────┘
                             │
                             ▼
                      ┌─────────────┐
                      │ Prometheus  │
                      └─────────────┘
```

## Image Size

The final Docker image is optimized to be under 20MB using a multi-stage build with Alpine Linux.

## Security

- Runs as non-root user (UID 1000)
- No unnecessary capabilities
- Minimal Alpine-based runtime
- CA certificates included for HTTPS

## License

Part of the Aletheia project.
