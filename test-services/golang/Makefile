.PHONY: help build build-macos-arm64 build-all run docker-build docker-build-arm64 docker-build-amd64 docker-run docker-load-kind docker-load-k3d k8s-deploy k8s-undeploy k8s-logs k8s-status k8s-port-forward test-errors test-health test-metrics clean deploy-all deploy-all-k3d

# Variables
IMAGE_NAME := aletheia/golang-test-service
IMAGE_TAG := latest
NAMESPACE := aletheia-test
SERVICE_NAME := golang-test-service

# Build variables
GOOS ?= $(shell go env GOOS)
GOARCH ?= $(shell go env GOARCH)
BINARY_NAME := main

help: ## Show this help message
	@echo "Aletheia Golang Test Service - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

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
	./main

docker-build: ## Build Docker image for current platform
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "✓ Image built: $(IMAGE_NAME):$(IMAGE_TAG)"

docker-build-arm64: ## Build Docker image for ARM64 (including macOS M1/M2)
	@echo "Building Docker image for ARM64..."
	docker build --build-arg TARGETOS=linux --build-arg TARGETARCH=arm64 -t $(IMAGE_NAME):$(IMAGE_TAG)-arm64 .
	@echo "✓ ARM64 image built: $(IMAGE_NAME):$(IMAGE_TAG)-arm64"

docker-build-amd64: ## Build Docker image for AMD64
	@echo "Building Docker image for AMD64..."
	docker build --build-arg TARGETOS=linux --build-arg TARGETARCH=amd64 -t $(IMAGE_NAME):$(IMAGE_TAG)-amd64 .
	@echo "✓ AMD64 image built: $(IMAGE_NAME):$(IMAGE_TAG)-amd64"

docker-run: ## Run Docker container locally
	@echo "Running Docker container..."
	$(MAKE) docker-build
	docker run --rm -p 8080:8080 -p 9090:9090 $(IMAGE_NAME):$(IMAGE_TAG)

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

k8s-deploy: ## Deploy to Kubernetes
	@echo "Deploying to Kubernetes..."
	kubectl apply -f ../k8s/golang/deployment.yaml
	kubectl apply -f ../k8s/golang/service.yaml
	@echo "✓ Deployed to namespace: $(NAMESPACE)"
	@echo ""
	@echo "Waiting for pods to be ready..."
	kubectl wait --for=condition=ready pod -l app=$(SERVICE_NAME) -n $(NAMESPACE) --timeout=60s || true
	@echo ""
	@echo "Status:"
	kubectl -n $(NAMESPACE) get pods,svc

k8s-undeploy: ## Remove from Kubernetes
	@echo "Removing from Kubernetes..."
	kubectl delete -f ../k8s/golang/service.yaml --ignore-not-found=true
	kubectl delete -f ../k8s/golang/deployment.yaml --ignore-not-found=true
	@echo "✓ Removed from Kubernetes"

k8s-logs: ## Show logs from Kubernetes pods
	@echo "Recent logs from $(SERVICE_NAME):"
	kubectl -n $(NAMESPACE) logs -l app=$(SERVICE_NAME) --tail=50 --all-containers=true

k8s-status: ## Show status of Kubernetes resources
	@echo "Status of $(SERVICE_NAME):"
	kubectl -n $(NAMESPACE) get pods,svc -l app=$(SERVICE_NAME)
	@echo ""
	@echo "Recent events:"
	kubectl -n $(NAMESPACE) get events --sort-by='.lastTimestamp' | tail -10

k8s-port-forward: ## Port forward service to localhost
	@echo "Port forwarding $(SERVICE_NAME) to localhost:8080 and :9090"
	kubectl -n $(NAMESPACE) port-forward svc/$(SERVICE_NAME) 8080:80 9090:9090

test-errors: ## Test all error endpoints (requires service running on localhost:8080)
	@echo "Testing error endpoints..."
	@echo "\n1. Testing nil_pointer error:"
	@curl -s http://localhost:8080/api/v1/error?type=nil_pointer || echo "Expected error"
	@sleep 1
	@echo "\n2. Testing index_out_of_bounds error:"
	@curl -s http://localhost:8080/api/v1/error?type=index_out_of_bounds || echo "Expected error"
	@sleep 1
	@echo "\n3. Testing divide_by_zero error:"
	@curl -s http://localhost:8080/api/v1/error?type=divide_by_zero || echo "Expected error"
	@sleep 1
	@echo "\n4. Testing json_unmarshal error:"
	@curl -s http://localhost:8080/api/v1/error?type=json_unmarshal | jq . 2>/dev/null || cat
	@sleep 1
	@echo "\n5. Testing db_timeout error:"
	@curl -s http://localhost:8080/api/v1/error?type=db_timeout | jq . 2>/dev/null || cat
	@echo "\n✓ All error tests completed"

test-health: ## Test health endpoints
	@echo "Testing health endpoints..."
	@echo "\nLiveness probe:"
	@curl -s http://localhost:8080/healthz
	@echo "\nReadiness probe:"
	@curl -s http://localhost:8080/readyz
	@echo "\n✓ Health check completed"

test-metrics: ## Show metrics
	@echo "Fetching metrics..."
	@curl -s http://localhost:9090/metrics | grep -E "(http_requests_total|error_count_total|panic_recovery_total)" || echo "No custom metrics yet"

clean: ## Clean build artifacts
	@echo "Cleaning..."
	rm -f main main-*
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
	@echo "  make k8s-port-forward"
	@echo "Then in another terminal:"
	@echo "  make test-errors"

# Quick deployment workflow for k3d
deploy-all-k3d: ## Build, load, and deploy (for k3d)
	$(MAKE) docker-build
	$(MAKE) docker-load-k3d
	$(MAKE) k8s-deploy
	@echo ""
	@echo "✓ Full deployment complete!"
	@echo ""
	@echo "To test, run:"
	@echo "  make k8s-port-forward"
	@echo "Then in another terminal:"
	@echo "  make test-errors"
