.PHONY: help build run test clean docker-build docker-run deploy undeploy logs

# Default target
help: ## Show this help message
	@echo "Aletheia Java Test Service - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

# Build targets
build: ## Build the Java application
	mvn clean package -DskipTests

build-macos-arm64: ## Build for macOS ARM64 (set JAVA_HOME if needed)
	@echo "Building for macOS ARM64..."
	mvn clean package -DskipTests
	@echo "✓ Built for macOS ARM64"

build-macos-amd64: ## Build for macOS AMD64 (set JAVA_HOME if needed)
	@echo "Building for macOS AMD64..."
	mvn clean package -DskipTests
	@echo "✓ Built for macOS AMD64"

build-all: ## Build for all platforms (simulated)
	@echo "Building for macOS ARM64..."
	$(MAKE) build-macos-arm64
	@echo "Building for macOS AMD64..."
	$(MAKE) build-macos-amd64
	@echo "✓ All builds complete"



# Docker variables
IMAGE_NAME := aletheia/java-test-service
IMAGE_TAG := latest
NAMESPACE := aletheia-test
SERVICE_NAME := java-test-service

.PHONY: docker-build docker-run docker-load-kind docker-load-k3d deploy

docker-build: ## Build Docker images (multi-arch)
	@echo "  HTTP: kubectl port-forward -n $(NAMESPACE) svc/$(SERVICE_NAME) 8080:80"
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "✓ Image built: $(IMAGE_NAME):$(IMAGE_TAG)"
	@echo "  Metrics: http://localhost:8080/actuator/prometheus"
	docker build --build-arg TARGETOS=linux --build-arg TARGETARCH=arm64 -t $(IMAGE_NAME):$(IMAGE_TAG)-arm64 .
	@echo "✓ ARM64 image built: $(IMAGE_NAME):$(IMAGE_TAG)-arm64"
	@echo "  Health: http://localhost:8080/actuator/health"
	docker build --build-arg TARGETOS=linux --build-arg TARGETARCH=amd64 -t $(IMAGE_NAME):$(IMAGE_TAG)-amd64 .
	@echo "✓ AMD64 image built: $(IMAGE_NAME):$(IMAGE_TAG)-amd64"

docker-run: ## Run Docker container locally
	docker run -p 8080:8080 --name java-test-service \
		-e JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0" \
		$(IMAGE_NAME):$(IMAGE_TAG)

docker-load-kind: ## Load Docker image into kind
	kind load docker-image $(IMAGE_NAME):$(IMAGE_TAG)
	@echo "✓ Image loaded into kind"

docker-load-k3d: ## Load Docker image into k3d
	k3d image import $(IMAGE_NAME):$(IMAGE_TAG)
	@echo "✓ Image loaded into k3d"

deploy: ## Deploy to Kubernetes
	kubectl delete -f ../k8s/java/ --ignore-not-found=true
	@echo "Deploying to Kubernetes..."
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -f ../k8s/java/
	@echo "Waiting for deployment to be ready..."
	kubectl wait --for=condition=available --timeout=120s deployment/$(SERVICE_NAME) -n $(NAMESPACE)
	@echo "✓ Deployed to namespace: $(NAMESPACE)"
	@echo ""
	@echo "Service endpoints:"
	@echo "  HTTP: kubectl port-forward -n $(NAMESPACE) svc/$(SERVICE_NAME) 8080:80"
	@echo "  Metrics: http://localhost:8080/actuator/prometheus"
	@echo "  Health: http://localhost:8080/actuator/health"

deploy-all: ## Build, load, and deploy (for kind)
	$(MAKE) docker-build
	$(MAKE) docker-load-kind
	$(MAKE) deploy
	@echo ""
	@echo "✓ Full deployment complete!"
	@echo ""
	@echo "To test, run:"
	@echo "  make k8s-port-forward"

deploy-all-k3d: ## Build, load, and deploy (for k3d)
	$(MAKE) docker-build
	$(MAKE) docker-load-k3d
	$(MAKE) deploy
	@echo ""
	@echo "✓ Full deployment complete!"
	@echo ""
	@echo "To test, run:"
	@echo "  make k8s-port-forward"


undeploy: ## Remove from Kubernetes
	kubectl delete -f ../k8s/java/ --ignore-not-found=true
	@echo "✓ Removed from Kubernetes"

k8s-port-forward: ## Port forward service to localhost

logs: ## Show logs from Kubernetes pods
	kubectl -n $(NAMESPACE) logs -l app=$(SERVICE_NAME) --tail=100 --all-containers=true -f

k8s-port-forward: ## Port forward service to localhost
	@echo "Port forwarding $(SERVICE_NAME) to localhost:8080"
	kubectl -n $(NAMESPACE) port-forward svc/$(SERVICE_NAME) 8080:80


# Trigger errors for testing
trigger-npe:
	curl "http://localhost:8080/api/v1/error?type=npe"

trigger-array-index:
	curl "http://localhost:8080/api/v1/error?type=array_index"

trigger-divide-by-zero:
	curl "http://localhost:8080/api/v1/error?type=divide_by_zero"

trigger-json-error:
	curl "http://localhost:8080/api/v1/error?type=json_error"

trigger-sql-error:
	curl "http://localhost:8080/api/v1/error?type=sql_error"

trigger-oom:
	curl "http://localhost:8080/api/v1/error?type=oom"
