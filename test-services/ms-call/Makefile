.PHONY: help build build-macos-arm64 build-all run docker-build docker-build-arm64 docker-build-amd64 docker-run docker-load-kind docker-load-k3d k8s-deploy k8s-undeploy k8s-logs k8s-status k8s-port-forward-caller k8s-port-forward-callee test-call test-called test-full-chain test-health clean deploy-all deploy-all-k3d

# Variables
IMAGE_NAME := ms-call
IMAGE_TAG := latest
NAMESPACE := default
SERVICE_NAME_CALLER := ms-call
SERVICE_NAME_CALLEE := ms-called

# Build variables
GOOS ?= $(shell go env GOOS)
GOARCH ?= $(shell go env GOARCH)
BINARY_NAME := ms-call

help: ## Show this help message
	@echo "ms-call Test Service - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

build: ## Build the Go binary locally
	@echo "Building Go binary for $(GOOS)/$(GOARCH)..."
	GOOS=$(GOOS) GOARCH=$(GOARCH) go build -o $(BINARY_NAME) .
	@echo "✓ Binary built: ./$(BINARY_NAME)"

build-macos-arm64: ## Build the Go binary for macOS ARM64
	@echo "Building Go binary for macOS ARM64..."
	GOOS=darwin GOARCH=arm64 go build -o $(BINARY_NAME)-darwin-arm64 .
	@echo "✓ Binary built: ./$(BINARY_NAME)-darwin-arm64"

build-all: ## Build binaries for multiple platforms
	@echo "Building for Linux AMD64..."
	@GOOS=linux GOARCH=amd64 go build -o $(BINARY_NAME)-linux-amd64 .
	@echo "Building for Linux ARM64..."
	@GOOS=linux GOARCH=arm64 go build -o $(BINARY_NAME)-linux-arm64 .
	@echo "Building for macOS ARM64..."
	@GOOS=darwin GOARCH=arm64 go build -o $(BINARY_NAME)-darwin-arm64 .
	@echo "Building for macOS AMD64..."
	@GOOS=darwin GOARCH=amd64 go build -o $(BINARY_NAME)-darwin-amd64 .
	@echo "✓ All binaries built"

run: ## Run the service locally
	@echo "Starting service..."
	$(MAKE) build
	./$(BINARY_NAME)

run-caller: ## Run as caller (calls itself)
	@echo "Starting service as caller..."
	$(MAKE) build
	DOWNSTREAM_URL=http://localhost:8080/api/v1/called ./$(BINARY_NAME)

docker-build: ## Build Docker image for current platform
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "✓ Image built: $(IMAGE_NAME):$(IMAGE_TAG)"

docker-build-arm64: ## Build Docker image for ARM64 (including macOS M1/M2)
	@echo "Building Docker image for ARM64..."
	docker buildx build --platform linux/arm64 -t $(IMAGE_NAME):$(IMAGE_TAG)-arm64 .
	@echo "✓ ARM64 image built: $(IMAGE_NAME):$(IMAGE_TAG)-arm64"

docker-build-amd64: ## Build Docker image for AMD64
	@echo "Building Docker image for AMD64..."
	docker buildx build --platform linux/amd64 -t $(IMAGE_NAME):$(IMAGE_TAG)-amd64 .
	@echo "✓ AMD64 image built: $(IMAGE_NAME):$(IMAGE_TAG)-amd64"

docker-run: ## Run Docker container locally
	@echo "Running Docker container..."
	$(MAKE) docker-build
	docker run --rm -p 8080:8080 $(IMAGE_NAME):$(IMAGE_TAG)

docker-load-kind: ## Load Docker image into kind cluster
	@echo "Loading image into kind..."
	$(MAKE) docker-build
	kind load docker-image $(IMAGE_NAME):$(IMAGE_TAG)
	@echo "✓ Image loaded into kind"

docker-load-k3d: ## Load Docker image into k3d cluster
	@echo "Loading image into k3d..."
	$(MAKE) docker-build
	k3d image import $(IMAGE_NAME):$(IMAGE_TAG)
	@echo "✓ Image loaded into k3d"

k8s-deploy: ## Deploy both caller and callee to Kubernetes
	@echo "Deploying to Kubernetes..."
	@echo "Deploying ms-called (callee)..."
	kubectl apply -f ../k8s/ms-call/ms-called-configmap.yaml
	kubectl apply -f ../k8s/ms-call/ms-called-deployment.yaml
	kubectl apply -f ../k8s/ms-call/ms-called-service.yaml
	@echo "Deploying ms-call (caller)..."
	kubectl apply -f ../k8s/ms-call/ms-call-configmap.yaml
	kubectl apply -f ../k8s/ms-call/ms-call-deployment.yaml
	kubectl apply -f ../k8s/ms-call/ms-call-service.yaml
	@echo "✓ Deployed to namespace: $(NAMESPACE)"
	@echo ""
	@echo "Waiting for pods to be ready..."
	kubectl wait --for=condition=ready pod -l app=$(SERVICE_NAME_CALLER) -n $(NAMESPACE) --timeout=60s || true
	kubectl wait --for=condition=ready pod -l app=$(SERVICE_NAME_CALLEE) -n $(NAMESPACE) --timeout=60s || true
	@echo ""
	@echo "Status:"
	kubectl -n $(NAMESPACE) get pods,svc -l 'app in (ms-call,ms-called)'

k8s-undeploy: ## Remove from Kubernetes
	@echo "Removing from Kubernetes..."
	kubectl delete -f ../k8s/ms-call/ms-call-service.yaml --ignore-not-found=true
	kubectl delete -f ../k8s/ms-call/ms-call-deployment.yaml --ignore-not-found=true
	kubectl delete -f ../k8s/ms-call/ms-call-configmap.yaml --ignore-not-found=true
	kubectl delete -f ../k8s/ms-call/ms-called-service.yaml --ignore-not-found=true
	kubectl delete -f ../k8s/ms-call/ms-called-deployment.yaml --ignore-not-found=true
	kubectl delete -f ../k8s/ms-call/ms-called-configmap.yaml --ignore-not-found=true
	@echo "✓ Removed from Kubernetes"

k8s-logs: ## Show logs from both services
	@echo "=== Logs from $(SERVICE_NAME_CALLER) (caller) ==="
	kubectl -n $(NAMESPACE) logs -l app=$(SERVICE_NAME_CALLER) --tail=20 --all-containers=true
	@echo ""
	@echo "=== Logs from $(SERVICE_NAME_CALLEE) (callee) ==="
	kubectl -n $(NAMESPACE) logs -l app=$(SERVICE_NAME_CALLEE) --tail=20 --all-containers=true

k8s-logs-caller: ## Show logs from caller service
	@echo "Logs from $(SERVICE_NAME_CALLER):"
	kubectl -n $(NAMESPACE) logs -l app=$(SERVICE_NAME_CALLER) --tail=50 --all-containers=true -f

k8s-logs-callee: ## Show logs from callee service (shows access logs)
	@echo "Logs from $(SERVICE_NAME_CALLEE):"
	kubectl -n $(NAMESPACE) logs -l app=$(SERVICE_NAME_CALLEE) --tail=50 --all-containers=true -f

k8s-status: ## Show status of Kubernetes resources
	@echo "Status of ms-call services:"
	kubectl -n $(NAMESPACE) get pods,svc -l 'app in (ms-call,ms-called)'
	@echo ""
	@echo "Recent events:"
	kubectl -n $(NAMESPACE) get events --sort-by='.lastTimestamp' | tail -10

k8s-port-forward-caller: ## Port forward caller service to localhost:8080
	@echo "Port forwarding $(SERVICE_NAME_CALLER) to localhost:8080"
	kubectl -n $(NAMESPACE) port-forward svc/$(SERVICE_NAME_CALLER) 8080:8080

k8s-port-forward-callee: ## Port forward callee service to localhost:8081
	@echo "Port forwarding $(SERVICE_NAME_CALLEE) to localhost:8081"
	kubectl -n $(NAMESPACE) port-forward svc/$(SERVICE_NAME_CALLEE) 8081:8080

test-call: ## Test /api/v1/call endpoint (requires service on localhost:8080)
	@echo "Testing /api/v1/call endpoint..."
	@curl -s -X POST http://localhost:8080/api/v1/call \
		-H "Content-Type: application/json" \
		-d '{"message":"test call","data":{"key":"value"}}' | jq .
	@echo "\n✓ Call test completed"

test-called: ## Test /api/v1/called endpoint (requires service on localhost:8080)
	@echo "Testing /api/v1/called endpoint..."
	@curl -s -X POST http://localhost:8080/api/v1/called \
		-H "Content-Type: application/json" \
		-d '{"message":"direct test","data":{"key":"value"}}' | jq .
	@echo "\n✓ Called test completed"

test-full-chain: ## Test full call chain (requires service on localhost:8080)
	@echo "Testing full call chain..."
	@echo "\n1. Testing direct call to /api/v1/called:"
	@curl -s http://localhost:8080/api/v1/called | jq .
	@echo "\n2. Testing call chain through /api/v1/call:"
	@curl -s -X POST http://localhost:8080/api/v1/call \
		-H "Content-Type: application/json" \
		-d '{"message":"chain test","data":{"test":"value"}}' | jq .
	@echo "\n✓ Full chain test completed"

test-health: ## Test health endpoint
	@echo "Testing health endpoint..."
	@curl -s http://localhost:8080/health | jq .
	@echo "\n✓ Health check completed"

test-k8s: ## Test services in Kubernetes (requires port-forward)
	@echo "Testing ms-call in Kubernetes..."
	@echo "Make sure to run 'make k8s-port-forward-caller' in another terminal first"
	@echo ""
	$(MAKE) test-full-chain

clean: ## Clean build artifacts
	@echo "Cleaning..."
	rm -f $(BINARY_NAME) $(BINARY_NAME)-*
	@echo "✓ Cleaned"

# Quick deployment workflow
deploy-all: ## Build, load, and deploy (for kind)
	$(MAKE) docker-build
	$(MAKE) docker-load-kind
	$(MAKE) k8s-deploy
	@echo ""
	@echo "✓ Full deployment complete!"
	@echo ""
	@echo "To test, run:"
	@echo "  make k8s-port-forward-caller"
	@echo "Then in another terminal:"
	@echo "  make test-full-chain"
	@echo "  make k8s-logs-callee  # to see access logs"

# Quick deployment workflow for k3d
deploy-all-k3d: ## Build, load, and deploy (for k3d)
	$(MAKE) docker-build
	$(MAKE) docker-load-k3d
	$(MAKE) k8s-deploy
	@echo ""
	@echo "✓ Full deployment complete!"
	@echo ""
	@echo "To test, run:"
	@echo "  make k8s-port-forward-caller"
	@echo "Then in another terminal:"
	@echo "  make test-full-chain"
	@echo "  make k8s-logs-callee  # to see access logs"
