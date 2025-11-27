# ms-call Service

A simple Go microservice that proxies HTTP calls to a downstream service.

## Overview

This service provides two main endpoints:

1. **`/api/v1/call`** - A client endpoint that calls a downstream service (configurable via `config.yaml` or environment variables)
2. **`/api/v1/called`** - A server endpoint that receives calls and logs access information including caller IP addresses

The service can act as both a caller and a receiver, making it useful for testing microservice communication patterns and observability scenarios in the Aletheia troubleshooting framework.

## Endpoints

### POST/GET /api/v1/call

Calls the downstream service at the configured URL (`/api/v1/called` by default).

**Request Body (optional):**
```json
{
  "message": "optional message",
  "data": {
    "key": "value"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully called downstream service",
  "downstream_status": 200,
  "downstream_body": {
    "response": "from downstream"
  }
}
```

### POST/GET /api/v1/called

Receives calls from the `/api/v1/call` endpoint (or any other client). This endpoint logs access information including the caller's IP address.

**Request Body (optional):**
```json
{
  "message": "optional message",
  "data": {
    "key": "value"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Request received successfully",
  "caller_ip": "192.168.1.100",
  "timestamp": "2025-11-27T10:30:00Z",
  "received": {
    "message": "optional message",
    "data": {
      "key": "value"
    }
  }
}
```

**Access Log Format:**
The endpoint logs each request with the following information:
```
[ACCESS LOG] endpoint=/api/v1/called method=POST caller_ip=192.168.1.100 timestamp=2025-11-27T10:30:00Z user_agent=ms-call/1.0
[ACCESS LOG] received_body=map[data:map[key:value] message:optional message]
```

**IP Address Detection:**
The endpoint intelligently detects the caller's IP address by checking:
1. `X-Forwarded-For` header (for requests through proxies/load balancers)
2. `X-Real-IP` header (for reverse proxy scenarios)
3. `RemoteAddr` (direct connection fallback)

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

## Configuration

Configuration can be provided via `config.yaml` or environment variables.

### config.yaml

```yaml
server:
  port: 8080

downstream:
  url: "http://localhost:8081/api/v1/called"
  timeout: 30s
```

### Environment Variables

- `PORT` - Server port (default: 8080)
- `DOWNSTREAM_URL` - Downstream service URL
- `CONFIG_PATH` - Path to config file (default: config.yaml)

## Quick Start with Makefile

A comprehensive Makefile is provided for easy building, testing, and deployment:

```bash
# Show all available commands
make help

# Build and run locally
make run

# Run as caller (calls itself)
make run-caller

# Build Docker image and run
make docker-run

# Deploy to Kubernetes (kind)
make deploy-all

# Deploy to Kubernetes (k3d)
make deploy-all-k3d

# Test the service
make test-full-chain
```

## Running Locally

### Prerequisites

- Go 1.21 or later

### Install Dependencies

```bash
go mod download
```

### Run with Makefile

```bash
# Build and run
make run

# Or run as caller (calls itself on localhost:8080)
make run-caller
```

### Run Manually

```bash
go run main.go
```

Or with custom downstream URL:

```bash
DOWNSTREAM_URL=http://localhost:9090/api/v1/called go run main.go
```

## Running with Docker

### Build Image

```bash
docker build -t ms-call:latest .
```

### Run Container

```bash
docker run -p 8080:8080 \
  -e DOWNSTREAM_URL=http://host.docker.internal:8081/api/v1/called \
  ms-call:latest
```

## Kubernetes Deployment

Kubernetes manifests are available in `../k8s/ms-call/` directory. See the [Kubernetes README](../k8s/ms-call/README.md) for detailed deployment instructions.

### Quick Deployment with Makefile

```bash
# Deploy to kind cluster
make deploy-all

# Deploy to k3d cluster
make deploy-all-k3d

# Check status
make k8s-status

# View logs (caller and callee)
make k8s-logs

# Port forward to test
make k8s-port-forward-caller  # In one terminal
make test-full-chain          # In another terminal

# Undeploy
make k8s-undeploy
```

## Testing

### Quick Testing with Makefile

```bash
# Test health endpoint
make test-health

# Test /api/v1/called endpoint
make test-called

# Test /api/v1/call endpoint
make test-call

# Test full call chain
make test-full-chain
```

### Manual Testing with curl

```bash
# Health check
curl http://localhost:8080/health

# Test /api/v1/called endpoint directly (GET)
curl http://localhost:8080/api/v1/called

# Test /api/v1/called endpoint (POST with body)
curl -X POST http://localhost:8080/api/v1/called \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "data": {"key": "value"}}'

# Call endpoint (GET) - will call downstream /api/v1/called
curl http://localhost:8080/api/v1/call

# Call endpoint (POST with body) - will forward to downstream
curl -X POST http://localhost:8080/api/v1/call \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "data": {"key": "value"}}'
```

### Testing the Full Call Chain

You can test the service calling itself:

```bash
# Start the service (it will call localhost:8081 by default)
# Update config to call itself on port 8080
DOWNSTREAM_URL=http://localhost:8080/api/v1/called ./ms-call

# In another terminal, call the /api/v1/call endpoint
curl -X POST http://localhost:8080/api/v1/call \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "data": {"test": "value"}}'

# Check the logs to see the access log from /api/v1/called
```

## Development

### Project Structure

```
ms-call/
├── main.go          # Main application code
├── config.yaml      # Configuration file
├── go.mod           # Go module definition
├── Dockerfile       # Docker build configuration
├── .dockerignore    # Docker ignore patterns
└── README.md        # This file
```

### Key Features

- Configurable downstream service URL
- Graceful shutdown handling
- Health check endpoint
- JSON request/response handling
- Timeout configuration
- Environment variable overrides
- Docker support

## License

Part of the Aletheia project.
