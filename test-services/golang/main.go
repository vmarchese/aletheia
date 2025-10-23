package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"strconv"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/google/uuid"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	// Metrics
	httpRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"endpoint", "status"},
	)

	httpRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"endpoint"},
	)

	errorCountTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "error_count_total",
			Help: "Total number of errors by type",
		},
		[]string{"error_type"},
	)

	panicRecoveryTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "panic_recovery_total",
			Help: "Total number of recovered panics",
		},
	)

	// Health check state
	livenessFailTime  int64 // Unix timestamp when liveness should start failing
	readinessFailTime int64 // Unix timestamp when readiness should start failing
	startTime         = time.Now()
	isReady           atomic.Bool
)

// LogEntry represents a structured log entry
type LogEntry struct {
	Timestamp   string                 `json:"timestamp"`
	Level       string                 `json:"level"`
	Message     string                 `json:"message"`
	RequestID   string                 `json:"request_id,omitempty"`
	ClientIP    string                 `json:"client_ip,omitempty"`
	Method      string                 `json:"method,omitempty"`
	Path        string                 `json:"path,omitempty"`
	Status      int                    `json:"status,omitempty"`
	Duration    int64                  `json:"duration_ms,omitempty"`
	Error       string                 `json:"error,omitempty"`
	ErrorType   string                 `json:"error_type,omitempty"`
	StackTrace  string                 `json:"stack_trace,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// logJSON logs a structured JSON entry to stdout
func logJSON(entry LogEntry) {
	if entry.Timestamp == "" {
		entry.Timestamp = time.Now().Format(time.RFC3339)
	}
	jsonBytes, _ := json.Marshal(entry)
	fmt.Println(string(jsonBytes))
}

// getStackTrace captures the current stack trace
func getStackTrace() string {
	buf := make([]byte, 4096)
	n := runtime.Stack(buf, false)
	return string(buf[:n])
}

// ErrorResponse represents an API error response
type ErrorResponse struct {
	Error     string `json:"error"`
	ErrorType string `json:"error_type"`
	Timestamp string `json:"timestamp"`
	RequestID string `json:"request_id"`
}

// loggingMiddleware wraps handlers with request logging
func loggingMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		requestID := uuid.New().String()

		// Add request ID to context
		ctx := context.WithValue(r.Context(), "request_id", requestID)
		r = r.WithContext(ctx)

		// Create a response writer wrapper to capture status code
		wrapped := &responseWriter{ResponseWriter: w, statusCode: 200}

		// Log request
		logJSON(LogEntry{
			Level:     "INFO",
			Message:   "Request received",
			RequestID: requestID,
			ClientIP:  r.RemoteAddr,
			Method:    r.Method,
			Path:      r.URL.Path,
		})

		// Handle the request with panic recovery
		func() {
			defer func() {
				if rec := recover(); rec != nil {
					panicRecoveryTotal.Inc()
					errorCountTotal.WithLabelValues("panic").Inc()

					stackTrace := getStackTrace()
					errorMsg := fmt.Sprintf("%v", rec)

					logJSON(LogEntry{
						Level:      "FATAL",
						Message:    "Panic recovered",
						RequestID:  requestID,
						Error:      errorMsg,
						ErrorType:  "panic",
						StackTrace: stackTrace,
					})

					wrapped.statusCode = http.StatusInternalServerError
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusInternalServerError)
					json.NewEncoder(w).Encode(ErrorResponse{
						Error:     errorMsg,
						ErrorType: "panic",
						Timestamp: time.Now().Format(time.RFC3339),
						RequestID: requestID,
					})
				}
			}()
			next(wrapped, r)
		}()

		// Log response
		duration := time.Since(start).Milliseconds()
		logEntry := LogEntry{
			Level:     "INFO",
			Message:   "Request completed",
			RequestID: requestID,
			Method:    r.Method,
			Path:      r.URL.Path,
			Status:    wrapped.statusCode,
			Duration:  duration,
		}

		if wrapped.statusCode >= 400 {
			logEntry.Level = "ERROR"
		}

		logJSON(logEntry)

		// Record metrics
		httpRequestsTotal.WithLabelValues(r.URL.Path, strconv.Itoa(wrapped.statusCode)).Inc()
		httpRequestDuration.WithLabelValues(r.URL.Path).Observe(float64(duration) / 1000.0)
	}
}

// responseWriter wraps http.ResponseWriter to capture status code
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// errorHandler handles the /api/v1/error endpoint
func errorHandler(w http.ResponseWriter, r *http.Request) {
	requestID := r.Context().Value("request_id").(string)
	errorType := r.URL.Query().Get("type")

	if errorType == "" {
		errorType = "nil_pointer"
	}

	logJSON(LogEntry{
		Level:     "WARN",
		Message:   fmt.Sprintf("Triggering intentional error: %s", errorType),
		RequestID: requestID,
		ErrorType: errorType,
	})

	errorCountTotal.WithLabelValues(errorType).Inc()

	switch errorType {
	case "nil_pointer":
		var ptr *string
		_ = *ptr // This will panic with nil pointer dereference

	case "index_out_of_bounds":
		arr := []int{1, 2, 3}
		_ = arr[10] // This will panic with index out of bounds

	case "divide_by_zero":
		x := 42
		y := 0
		_ = x / y // This will panic with integer divide by zero

	case "json_unmarshal":
		var data map[string]interface{}
		invalidJSON := `{"broken": json}`
		err := json.Unmarshal([]byte(invalidJSON), &data)
		if err != nil {
			logJSON(LogEntry{
				Level:      "ERROR",
				Message:    "JSON unmarshal error",
				RequestID:  requestID,
				Error:      err.Error(),
				ErrorType:  "json_unmarshal",
				StackTrace: getStackTrace(),
			})
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(ErrorResponse{
				Error:     err.Error(),
				ErrorType: "json_unmarshal",
				Timestamp: time.Now().Format(time.RFC3339),
				RequestID: requestID,
			})
			return
		}

	case "db_timeout":
		logJSON(LogEntry{
			Level:     "ERROR",
			Message:   "Simulated database connection timeout",
			RequestID: requestID,
			Error:     "connection timeout after 30s",
			ErrorType: "db_timeout",
			Metadata: map[string]interface{}{
				"database": "postgres",
				"timeout":  "30s",
				"query":    "SELECT * FROM users WHERE id = ?",
			},
		})
		time.Sleep(100 * time.Millisecond) // Simulate delay
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(ErrorResponse{
			Error:     "database connection timeout",
			ErrorType: "db_timeout",
			Timestamp: time.Now().Format(time.RFC3339),
			RequestID: requestID,
		})
		return

	default:
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{
			Error:     fmt.Sprintf("unknown error type: %s", errorType),
			ErrorType: "invalid_request",
			Timestamp: time.Now().Format(time.RFC3339),
			RequestID: requestID,
		})
		return
	}
}

// randomHandler handles the /api/v1/random endpoint with random delay
func randomHandler(w http.ResponseWriter, r *http.Request) {
	requestID := r.Context().Value("request_id").(string)

	// Generate random delay between 0-5 seconds
	delay := time.Duration(rand.Float64() * 5 * float64(time.Second))

	logJSON(LogEntry{
		Level:     "INFO",
		Message:   fmt.Sprintf("Random endpoint called, sleeping for %v", delay),
		RequestID: requestID,
		Metadata: map[string]interface{}{
			"delay_seconds": delay.Seconds(),
		},
	})

	// Sleep for the random duration
	time.Sleep(delay)

	// Return success response
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":        "success",
		"message":       "Random endpoint response",
		"delay_seconds": delay.Seconds(),
		"timestamp":     time.Now().Format(time.RFC3339),
		"request_id":    requestID,
	})
}

// healthzHandler handles the /healthz liveness probe
func healthzHandler(w http.ResponseWriter, r *http.Request) {
	requestID := r.Context().Value("request_id").(string)

	// Check if we should fail liveness
	failTime := atomic.LoadInt64(&livenessFailTime)
	if failTime > 0 && time.Now().Unix() >= failTime {
		logJSON(LogEntry{
			Level:     "ERROR",
			Message:   "Liveness check failed (configured failure)",
			RequestID: requestID,
		})
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte("liveness check failed\n"))
		return
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("ok\n"))
}

// readyzHandler handles the /readyz readiness probe
func readyzHandler(w http.ResponseWriter, r *http.Request) {
	requestID := r.Context().Value("request_id").(string)

	// Check if we should fail readiness
	failTime := atomic.LoadInt64(&readinessFailTime)
	if failTime > 0 && time.Now().Unix() >= failTime {
		logJSON(LogEntry{
			Level:     "ERROR",
			Message:   "Readiness check failed (configured failure)",
			RequestID: requestID,
		})
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte("readiness check failed\n"))
		return
	}

	// Check if service is ready
	if !isReady.Load() {
		logJSON(LogEntry{
			Level:     "WARN",
			Message:   "Readiness check failed (service not ready)",
			RequestID: requestID,
		})
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte("service not ready\n"))
		return
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("ok\n"))
}

// rootHandler handles the root endpoint
func rootHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"service":  "aletheia-golang-test-service",
		"version":  "1.0.0",
		"uptime":   time.Since(startTime).String(),
		"ready":    isReady.Load(),
		"endpoints": []string{
			"GET /",
			"GET /api/v1/error?type={nil_pointer|index_out_of_bounds|divide_by_zero|json_unmarshal|db_timeout}",
			"GET /api/v1/random",
			"GET /healthz",
			"GET /readyz",
			"GET /metrics",
		},
	})
}

func main() {
	// Configure structured logging
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelDebug,
	}))
	slog.SetDefault(logger)

	// Parse configuration from environment
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	metricsPort := os.Getenv("METRICS_PORT")
	if metricsPort == "" {
		metricsPort = "9090"
	}

	startupDelay := os.Getenv("STARTUP_DELAY")
	if startupDelay != "" {
		if delay, err := time.ParseDuration(startupDelay); err == nil {
			logJSON(LogEntry{
				Level:   "INFO",
				Message: fmt.Sprintf("Startup delay configured: %s", delay),
			})
			time.Sleep(delay)
		}
	}

	// Configure failure scenarios
	if failAfter := os.Getenv("FAIL_LIVENESS_AFTER"); failAfter != "" {
		if duration, err := time.ParseDuration(failAfter); err == nil {
			failTime := time.Now().Add(duration).Unix()
			atomic.StoreInt64(&livenessFailTime, failTime)
			logJSON(LogEntry{
				Level:   "WARN",
				Message: fmt.Sprintf("Liveness will fail after %s", duration),
			})
		}
	}

	if failAfter := os.Getenv("FAIL_READINESS_AFTER"); failAfter != "" {
		if duration, err := time.ParseDuration(failAfter); err == nil {
			failTime := time.Now().Add(duration).Unix()
			atomic.StoreInt64(&readinessFailTime, failTime)
			logJSON(LogEntry{
				Level:   "WARN",
				Message: fmt.Sprintf("Readiness will fail after %s", duration),
			})
		}
	}

	// Mark service as ready
	isReady.Store(true)

	// Set up HTTP routes
	mux := http.NewServeMux()
	mux.HandleFunc("/", loggingMiddleware(rootHandler))
	mux.HandleFunc("/api/v1/error", loggingMiddleware(errorHandler))
	mux.HandleFunc("/api/v1/random", loggingMiddleware(randomHandler))
	mux.HandleFunc("/healthz", loggingMiddleware(healthzHandler))
	mux.HandleFunc("/readyz", loggingMiddleware(readyzHandler))

	// Set up metrics server
	metricsMux := http.NewServeMux()
	metricsMux.Handle("/metrics", promhttp.Handler())

	// Start main HTTP server
	server := &http.Server{
		Addr:    ":" + port,
		Handler: mux,
	}

	metricsServer := &http.Server{
		Addr:    ":" + metricsPort,
		Handler: metricsMux,
	}

	// Start servers in goroutines
	go func() {
		logJSON(LogEntry{
			Level:   "INFO",
			Message: fmt.Sprintf("Starting HTTP server on port %s", port),
		})
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logJSON(LogEntry{
				Level:   "FATAL",
				Message: "HTTP server failed",
				Error:   err.Error(),
			})
			os.Exit(1)
		}
	}()

	go func() {
		logJSON(LogEntry{
			Level:   "INFO",
			Message: fmt.Sprintf("Starting metrics server on port %s", metricsPort),
		})
		if err := metricsServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logJSON(LogEntry{
				Level:   "FATAL",
				Message: "Metrics server failed",
				Error:   err.Error(),
			})
			os.Exit(1)
		}
	}()

	logJSON(LogEntry{
		Level:   "INFO",
		Message: "Service started successfully",
		Metadata: map[string]interface{}{
			"http_port":    port,
			"metrics_port": metricsPort,
		},
	})

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	<-sigChan

	logJSON(LogEntry{
		Level:   "INFO",
		Message: "Shutting down gracefully...",
	})

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		logJSON(LogEntry{
			Level:   "ERROR",
			Message: "HTTP server shutdown error",
			Error:   err.Error(),
		})
	}

	if err := metricsServer.Shutdown(ctx); err != nil {
		logJSON(LogEntry{
			Level:   "ERROR",
			Message: "Metrics server shutdown error",
			Error:   err.Error(),
		})
	}

	logJSON(LogEntry{
		Level:   "INFO",
		Message: "Service stopped",
	})
}
