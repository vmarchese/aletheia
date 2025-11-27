package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"gopkg.in/yaml.v3"
)

// Config represents the application configuration
type Config struct {
	Server struct {
		Port string `yaml:"port"`
	} `yaml:"server"`
	Downstream struct {
		URL     string        `yaml:"url"`
		Timeout time.Duration `yaml:"timeout"`
	} `yaml:"downstream"`
}

// Server holds the application state
type Server struct {
	config     *Config
	httpClient *http.Client
	router     *mux.Router
}

// CallRequest represents the request body for /api/v1/call
type CallRequest struct {
	Message string                 `json:"message,omitempty"`
	Data    map[string]interface{} `json:"data,omitempty"`
}

// CallResponse represents the response from /api/v1/call
type CallResponse struct {
	Status           string                 `json:"status"`
	Message          string                 `json:"message,omitempty"`
	DownstreamStatus int                    `json:"downstream_status,omitempty"`
	DownstreamBody   map[string]interface{} `json:"downstream_body,omitempty"`
	Error            string                 `json:"error,omitempty"`
}

// CalledResponse represents the response from /api/v1/called
type CalledResponse struct {
	Status    string                 `json:"status"`
	Message   string                 `json:"message"`
	CallerIP  string                 `json:"caller_ip"`
	Timestamp string                 `json:"timestamp"`
	Received  map[string]interface{} `json:"received,omitempty"`
}

// loadConfig loads configuration from file
func loadConfig(configPath string) (*Config, error) {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var config Config
	if err := yaml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	return &config, nil
}

// NewServer creates a new server instance
func NewServer(config *Config) *Server {
	s := &Server{
		config: config,
		httpClient: &http.Client{
			Timeout: config.Downstream.Timeout,
		},
		router: mux.NewRouter(),
	}

	s.setupRoutes()
	return s
}

// setupRoutes configures the HTTP routes
func (s *Server) setupRoutes() {
	s.router.HandleFunc("/api/v1/call", s.handleCall).Methods("POST", "GET")
	s.router.HandleFunc("/api/v1/called", s.handleCalled).Methods("POST", "GET")
	s.router.HandleFunc("/health", s.handleHealth).Methods("GET")
}

// handleCall handles the /api/v1/call endpoint
func (s *Server) handleCall(w http.ResponseWriter, r *http.Request) {
	log.Printf("Received request: %s %s from %s", r.Method, r.URL.Path, r.RemoteAddr)

	// Parse request body if present
	var reqBody CallRequest
	if r.Body != nil && r.Method == "POST" {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&reqBody); err != nil {
			log.Printf("Failed to decode request body: %v", err)
			// Continue anyway, body is optional
		}
	}

	// Call downstream service
	downstreamResp, err := s.callDownstream(r.Context(), reqBody)
	if err != nil {
		log.Printf("Error calling downstream service: %v", err)
		s.sendJSON(w, http.StatusBadGateway, CallResponse{
			Status:  "error",
			Message: "Failed to call downstream service",
			Error:   err.Error(),
		})
		return
	}

	// Parse downstream response
	var downstreamBody map[string]interface{}
	if downstreamResp.Body != nil {
		defer downstreamResp.Body.Close()
		bodyBytes, err := io.ReadAll(downstreamResp.Body)
		if err != nil {
			log.Printf("Failed to read downstream response: %v", err)
		} else {
			if err := json.Unmarshal(bodyBytes, &downstreamBody); err != nil {
				log.Printf("Failed to parse downstream response: %v", err)
				// Store raw response as string
				downstreamBody = map[string]interface{}{
					"raw": string(bodyBytes),
				}
			}
		}
	}

	// Send response
	response := CallResponse{
		Status:           "success",
		Message:          "Successfully called downstream service",
		DownstreamStatus: downstreamResp.StatusCode,
		DownstreamBody:   downstreamBody,
	}

	statusCode := http.StatusOK
	if downstreamResp.StatusCode >= 400 {
		response.Status = "partial_success"
		response.Message = "Downstream service returned error status"
	}

	log.Printf("Downstream response status: %d", downstreamResp.StatusCode)
	s.sendJSON(w, statusCode, response)
}

// callDownstream makes an HTTP call to the downstream service
func (s *Server) callDownstream(ctx context.Context, reqBody CallRequest) (*http.Response, error) {
	url := s.config.Downstream.URL
	log.Printf("Calling downstream service: %s", url)

	// Create request body if present
	var body io.Reader = http.NoBody
	if reqBody.Message != "" || len(reqBody.Data) > 0 {
		jsonBody, err := json.Marshal(reqBody)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
		body = bytes.NewReader(jsonBody)
		log.Printf("Sending body to downstream: %s", string(jsonBody))
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, body)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "ms-call/1.0")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to call downstream: %w", err)
	}

	return resp, nil
}

// handleCalled handles the /api/v1/called endpoint
func (s *Server) handleCalled(w http.ResponseWriter, r *http.Request) {
	// Extract caller IP
	callerIP := s.getClientIP(r)
	timestamp := time.Now().Format(time.RFC3339)

	// Log access with caller IP
	log.Printf("[ACCESS LOG] endpoint=/api/v1/called method=%s caller_ip=%s timestamp=%s user_agent=%s",
		r.Method, callerIP, timestamp, r.Header.Get("User-Agent"))

	// Parse request body if present
	var reqBody map[string]interface{}
	if r.Body != nil && r.Method == "POST" {
		defer r.Body.Close()
		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			log.Printf("Failed to read request body: %v", err)
		} else if len(bodyBytes) > 0 {
			if err := json.Unmarshal(bodyBytes, &reqBody); err != nil {
				log.Printf("Failed to parse request body: %v", err)
				// Store raw body if JSON parsing fails
				reqBody = map[string]interface{}{
					"raw": string(bodyBytes),
				}
			}
			log.Printf("[ACCESS LOG] received_body=%v", reqBody)
		}
	}

	// Send response
	response := CalledResponse{
		Status:    "success",
		Message:   "Request received successfully",
		CallerIP:  callerIP,
		Timestamp: timestamp,
		Received:  reqBody,
	}

	s.sendJSON(w, http.StatusOK, response)
}

// getClientIP extracts the real client IP from the request
func (s *Server) getClientIP(r *http.Request) string {
	// Check X-Forwarded-For header first (for proxy/load balancer scenarios)
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		// X-Forwarded-For can contain multiple IPs, get the first one
		for idx := 0; idx < len(xff); idx++ {
			if xff[idx] == ',' {
				return xff[:idx]
			}
		}
		return xff
	}

	// Check X-Real-IP header
	if xri := r.Header.Get("X-Real-IP"); xri != "" {
		return xri
	}

	// Fall back to RemoteAddr
	return r.RemoteAddr
}

// handleHealth handles the /health endpoint
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	s.sendJSON(w, http.StatusOK, map[string]string{
		"status": "healthy",
	})
}

// sendJSON sends a JSON response
func (s *Server) sendJSON(w http.ResponseWriter, statusCode int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	if err := json.NewEncoder(w).Encode(data); err != nil {
		log.Printf("Failed to encode JSON response: %v", err)
	}
}

// Start starts the HTTP server
func (s *Server) Start() error {
	addr := ":" + s.config.Server.Port
	srv := &http.Server{
		Addr:         addr,
		Handler:      s.router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Graceful shutdown handling
	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		log.Printf("Starting server on %s", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	<-done
	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		return fmt.Errorf("server shutdown failed: %w", err)
	}

	log.Println("Server stopped gracefully")
	return nil
}

func main() {
	// Load configuration
	configPath := os.Getenv("CONFIG_PATH")
	if configPath == "" {
		configPath = "config.yaml"
	}

	config, err := loadConfig(configPath)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Override with environment variables if present
	if port := os.Getenv("PORT"); port != "" {
		config.Server.Port = port
	}
	if downstreamURL := os.Getenv("DOWNSTREAM_URL"); downstreamURL != "" {
		config.Downstream.URL = downstreamURL
	}

	// Create and start server
	server := NewServer(config)
	if err := server.Start(); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
