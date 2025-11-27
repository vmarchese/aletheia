# Kubernetes Deployment for ms-call Test Services

This directory contains Kubernetes manifests for deploying the ms-call test services in a Kubernetes cluster.

## Architecture

The deployment consists of two separate services:

1. **ms-call (Caller)** - Makes HTTP calls to the downstream service
2. **ms-called (Callee)** - Receives HTTP calls and logs access information

```
┌─────────────┐         ┌──────────────┐
│   ms-call   │────────▶│  ms-called   │
│  (caller)   │  HTTP   │  (callee)    │
│  Port 8080  │         │  Port 8080   │
└─────────────┘         └──────────────┘
     │                         │
     │                         │
   /api/v1/call          /api/v1/called
                         (logs caller IP)
```

## Files

### ms-call (Caller) Resources
- `ms-call-configmap.yaml` - Configuration with downstream URL pointing to ms-called service
- `ms-call-deployment.yaml` - Deployment with 2 replicas
- `ms-call-service.yaml` - ClusterIP service exposing port 8080

### ms-called (Callee) Resources
- `ms-called-configmap.yaml` - Configuration for the receiver service
- `ms-called-deployment.yaml` - Deployment with 2 replicas
- `ms-called-service.yaml` - ClusterIP service exposing port 8080

## Prerequisites

1. Kubernetes cluster (minikube, kind, or any K8s cluster)
2. kubectl configured to access your cluster
3. Docker image built and available to the cluster

## Building the Docker Image

From the `test-services/ms-call` directory:

```bash
# Build the Docker image
cd ../../ms-call
docker build -t ms-call:latest .

# If using minikube, load the image into minikube
minikube image load ms-call:latest

# If using kind, load the image into kind
kind load docker-image ms-call:latest
```

## Deployment

### Deploy All Resources

```bash
# Deploy all resources at once
kubectl apply -f ms-called-configmap.yaml \
              -f ms-called-deployment.yaml \
              -f ms-called-service.yaml \
              -f ms-call-configmap.yaml \
              -f ms-call-deployment.yaml \
              -f ms-call-service.yaml
```

### Deploy Individually

```bash
# Deploy ms-called (callee) first
kubectl apply -f ms-called-configmap.yaml
kubectl apply -f ms-called-deployment.yaml
kubectl apply -f ms-called-service.yaml

# Deploy ms-call (caller)
kubectl apply -f ms-call-configmap.yaml
kubectl apply -f ms-call-deployment.yaml
kubectl apply -f ms-call-service.yaml
```

## Verification

### Check Deployment Status

```bash
# Check if pods are running
kubectl get pods -l app=ms-call
kubectl get pods -l app=ms-called

# Check services
kubectl get svc ms-call ms-called

# Check deployments
kubectl get deployment ms-call ms-called
```

### View Logs

```bash
# View ms-called logs (should show access logs)
kubectl logs -l app=ms-called -f

# View ms-call logs
kubectl logs -l app=ms-call -f
```

## Testing

### Test from Within the Cluster

```bash
# Create a test pod
kubectl run test-pod --image=curlimages/curl:latest --rm -it --restart=Never -- sh

# From inside the pod:
# Test ms-called directly
curl http://ms-called:8080/api/v1/called

# Test the full chain through ms-call
curl -X POST http://ms-call:8080/api/v1/call \
  -H "Content-Type: application/json" \
  -d '{"message": "test from k8s", "data": {"key": "value"}}'
```

### Test via Port Forward

```bash
# Forward ms-call service to localhost
kubectl port-forward svc/ms-call 8080:8080

# In another terminal, test the endpoint
curl -X POST http://localhost:8080/api/v1/call \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "data": {"key": "value"}}'

# Check ms-called logs to see the access log
kubectl logs -l app=ms-called --tail=20
```

Expected log output from ms-called:
```
[ACCESS LOG] endpoint=/api/v1/called method=POST caller_ip=10.244.0.5:45678 timestamp=2025-11-27T10:30:00Z user_agent=ms-call/1.0
[ACCESS LOG] received_body=map[data:map[key:value] message:test]
```

## Scaling

```bash
# Scale ms-call
kubectl scale deployment ms-call --replicas=3

# Scale ms-called
kubectl scale deployment ms-called --replicas=3

# Verify scaling
kubectl get pods -l app=ms-call
kubectl get pods -l app=ms-called
```

## Configuration Changes

To change the downstream URL for ms-call:

```bash
# Edit the configmap
kubectl edit configmap ms-call-config

# Restart the deployment to pick up changes
kubectl rollout restart deployment ms-call
```

## Cleanup

```bash
# Delete all resources
kubectl delete -f ms-call-service.yaml \
               -f ms-call-deployment.yaml \
               -f ms-call-configmap.yaml \
               -f ms-called-service.yaml \
               -f ms-called-deployment.yaml \
               -f ms-called-configmap.yaml

# Or delete by label
kubectl delete all,configmap -l component=caller
kubectl delete all,configmap -l component=callee
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod -l app=ms-call
kubectl describe pod -l app=ms-called

# Common issues:
# - Image not available (ImagePullBackOff)
# - Resource constraints (Pending)
# - Configuration errors (CrashLoopBackOff)
```

### Service Communication Issues

```bash
# Check if services are resolving
kubectl run test-dns --image=busybox:latest --rm -it --restart=Never -- nslookup ms-called

# Check service endpoints
kubectl get endpoints ms-call ms-called

# Verify service is routing to pods
kubectl describe svc ms-call
kubectl describe svc ms-called
```

### Configuration Not Loading

```bash
# Verify configmap exists and has correct data
kubectl describe configmap ms-call-config
kubectl describe configmap ms-called-config

# Check if configmap is mounted in pod
kubectl exec -it $(kubectl get pod -l app=ms-call -o jsonpath='{.items[0].metadata.name}') -- cat /config/config.yaml
```

## Advanced Usage

### Using Different Namespaces

```bash
# Create a namespace
kubectl create namespace aletheia-test

# Deploy to specific namespace
kubectl apply -f . -n aletheia-test

# Access services across namespaces
# Service URL format: <service-name>.<namespace>.svc.cluster.local
# Update ms-call configmap to use: http://ms-called.aletheia-test.svc.cluster.local:8080/api/v1/called
```

### Network Policies

Example network policy to restrict ms-call to only communicate with ms-called:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ms-call-policy
spec:
  podSelector:
    matchLabels:
      app: ms-call
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: ms-called
    ports:
    - protocol: TCP
      port: 8080
```

## Monitoring

### Prometheus Metrics

If using Prometheus, add these annotations to the deployment:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
```

### Health Checks

Both services expose a `/health` endpoint used by:
- Liveness probes (restart unhealthy pods)
- Readiness probes (remove from service endpoints when not ready)

```bash
# Check health manually
kubectl exec -it $(kubectl get pod -l app=ms-call -o jsonpath='{.items[0].metadata.name}') -- wget -O- http://localhost:8080/health
```

## Integration with Aletheia

These services are designed for testing Aletheia's troubleshooting capabilities:

1. **Log Analysis**: ms-called generates structured access logs with caller IP information
2. **Service Mesh Testing**: Test service-to-service communication patterns
3. **Network Debugging**: Verify connectivity and DNS resolution between services
4. **Performance Testing**: Load test with multiple replicas and observe behavior

Example Aletheia use case:
```bash
# Generate traffic
kubectl run load-generator --image=williamyeh/wrk --rm -it --restart=Never -- \
  -t4 -c100 -d30s http://ms-call:8080/api/v1/call

# Analyze logs with Aletheia
aletheia analyze logs --service ms-called --filter "ACCESS LOG"
```
