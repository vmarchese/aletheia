.PHONY: help build run test clean docker-build docker-run deploy undeploy logs

# Default target
help:
	@echo "Available targets:"
	@echo "  build         - Build the Java application"
	@echo "  run           - Run the application locally"
	@echo "  test          - Run tests"
	@echo "  clean         - Clean build artifacts"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run Docker container locally"
	@echo "  deploy        - Deploy to Kubernetes"
	@echo "  undeploy      - Remove from Kubernetes"
	@echo "  logs          - View application logs"

# Build the application
build:
	mvn clean package -DskipTests

# Run locally
run:
	mvn spring-boot:run

# Run tests
test:
	mvn test

# Clean build artifacts
clean:
	mvn clean

# Build Docker image
docker-build:
	docker build -t aletheia/java-test-service:1.0.0 .

# Run Docker container locally
docker-run: docker-build
	docker run -p 8080:8080 --name java-test-service \
		-e JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0" \
		aletheia/java-test-service:1.0.0

# Deploy to Kubernetes
deploy: docker-build
	@echo "Loading image into kind/k3d cluster (if using local cluster)..."
	-kind load docker-image aletheia/java-test-service:1.0.0 2>/dev/null || \
	 k3d image import aletheia/java-test-service:1.0.0 2>/dev/null || \
	 echo "Not using kind/k3d, assuming image is available in registry"
	@echo "Creating namespace..."
	kubectl create namespace aletheia-test --dry-run=client -o yaml | kubectl apply -f -
	@echo "Applying Kubernetes manifests..."
	kubectl apply -f ../k8s/java/
	@echo "Waiting for deployment to be ready..."
	kubectl wait --for=condition=available --timeout=120s deployment/java-test-service -n aletheia-test
	@echo "Deployment complete!"
	@echo ""
	@echo "Service endpoints:"
	@echo "  HTTP: kubectl port-forward -n aletheia-test svc/java-test-service 8080:80"
	@echo "  Metrics: http://localhost:8080/actuator/prometheus"
	@echo "  Health: http://localhost:8080/actuator/health"

# Undeploy from Kubernetes
undeploy:
	kubectl delete -f ../k8s/java/ --ignore-not-found=true
	@echo "Undeployed successfully"

# View logs
logs:
	kubectl logs -n aletheia-test -l app=java-test-service --tail=100 -f

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
