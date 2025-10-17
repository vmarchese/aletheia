"""Demo data provider with pre-recorded responses and mock data.

This module provides pre-recorded data for various investigation scenarios
to enable testing of the guided mode workflow without real data sources.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


class DemoDataProvider:
    """Provides pre-recorded demo data for testing."""
    
    def __init__(self, scenario: str = "payment_service_crash"):
        """Initialize with a specific scenario.
        
        Args:
            scenario: Name of the demo scenario to use
        """
        self.scenario = scenario
        self._current_time = datetime.now()
    
    def get_kubernetes_logs(self, pod: str, namespace: str = "default", 
                           since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pre-recorded Kubernetes logs.
        
        Args:
            pod: Pod name
            namespace: Kubernetes namespace
            since: Time window (e.g., "1h")
        
        Returns:
            List of log entries with timestamps and messages
        """
        if self.scenario == "payment_service_crash":
            return self._get_payment_service_logs()
        elif self.scenario == "api_latency_spike":
            return self._get_api_latency_logs()
        else:
            return []
    
    def get_prometheus_metrics(self, query: str, start: datetime, 
                               end: datetime) -> List[Dict[str, Any]]:
        """Get pre-recorded Prometheus metrics.
        
        Args:
            query: PromQL query
            start: Start time
            end: End time
        
        Returns:
            List of metric data points
        """
        if self.scenario == "payment_service_crash":
            return self._get_payment_service_metrics(start, end)
        elif self.scenario == "api_latency_spike":
            return self._get_api_latency_metrics(start, end)
        else:
            return []
    
    def get_git_blame(self, file_path: str, line_number: int, 
                     repo: str) -> Dict[str, Any]:
        """Get pre-recorded git blame information.
        
        Args:
            file_path: Path to file in repository
            line_number: Line number to blame
            repo: Repository path
        
        Returns:
            Git blame information (author, commit, date, message)
        """
        if self.scenario == "payment_service_crash":
            return {
                "author": "jane.doe@example.com",
                "commit": "a1b2c3d4",
                "date": "2025-10-15",
                "message": "feat: add concurrent payment processing",
                "line": line_number,
                "file": file_path,
            }
        else:
            return {
                "author": "john.smith@example.com",
                "commit": "e5f6g7h8",
                "date": "2025-10-16",
                "message": "fix: update API timeout configuration",
                "line": line_number,
                "file": file_path,
            }
    
    def get_code_context(self, file_path: str, line_number: int, 
                        context_lines: int = 10) -> str:
        """Get pre-recorded code context.
        
        Args:
            file_path: Path to file
            line_number: Center line number
            context_lines: Number of lines before/after
        
        Returns:
            Code snippet with context
        """
        if self.scenario == "payment_service_crash":
            return """
func ProcessPayment(ctx context.Context, payment *Payment) error {
    // Acquire lock for payment processing
    if err := acquireLock(payment.ID); err != nil {
        return fmt.Errorf("failed to acquire lock: %w", err)
    }
    
    // BUG: Lock is never released if validation fails
    if err := validatePayment(payment); err != nil {
        return fmt.Errorf("validation failed: %w", err)
    }
    
    defer releaseLock(payment.ID)  // This line comes too late!
    
    // Process the payment
    result, err := processTransaction(ctx, payment)
    if err != nil {
        return fmt.Errorf("transaction failed: %w", err)
    }
    
    return nil
}
"""
        else:
            return """
func HandleAPIRequest(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    
    // BUG: Timeout set too low for complex queries
    ctx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
    defer cancel()
    
    result, err := queryDatabase(ctx, r.URL.Query())
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    
    json.NewEncoder(w).Encode(result)
}
"""
    
    def _get_payment_service_logs(self) -> List[Dict[str, Any]]:
        """Get logs for payment service crash scenario."""
        base_time = self._current_time - timedelta(hours=1)
        
        logs = []
        # Normal operation for first 45 minutes
        for i in range(10):
            logs.append({
                "timestamp": (base_time + timedelta(minutes=i*4)).isoformat(),
                "level": "INFO",
                "message": f"Payment {1000+i} processed successfully",
                "pod": "payment-service-7d9f8b-abc12",
            })
        
        # Errors start appearing
        error_time = base_time + timedelta(minutes=45)
        for i in range(20):
            logs.append({
                "timestamp": (error_time + timedelta(seconds=i*10)).isoformat(),
                "level": "ERROR",
                "message": f"Failed to acquire lock for payment {2000+i}: context deadline exceeded",
                "pod": "payment-service-7d9f8b-abc12",
                "stack_trace": "goroutine 42 [running]:\nmain.ProcessPayment(0xc0001a0000)\n\t/app/payment.go:45 +0x123",
            })
        
        # Critical errors and crashes
        crash_time = error_time + timedelta(minutes=5)
        for i in range(5):
            logs.append({
                "timestamp": (crash_time + timedelta(seconds=i*5)).isoformat(),
                "level": "FATAL",
                "message": "Too many goroutines blocked, service unresponsive",
                "pod": "payment-service-7d9f8b-abc12",
            })
        
        return logs
    
    def _get_api_latency_logs(self) -> List[Dict[str, Any]]:
        """Get logs for API latency spike scenario."""
        base_time = self._current_time - timedelta(hours=2)
        
        logs = []
        # Normal requests
        for i in range(15):
            logs.append({
                "timestamp": (base_time + timedelta(minutes=i*5)).isoformat(),
                "level": "INFO",
                "message": f"API request completed in {20+i*2}ms",
                "pod": "api-gateway-5c8d9a-xyz34",
            })
        
        # Timeout errors start
        error_time = base_time + timedelta(hours=1, minutes=30)
        for i in range(30):
            logs.append({
                "timestamp": (error_time + timedelta(seconds=i*15)).isoformat(),
                "level": "ERROR",
                "message": f"Request timeout after 100ms: context deadline exceeded",
                "pod": "api-gateway-5c8d9a-xyz34",
                "stack_trace": "at HandleAPIRequest (/app/api.go:78)",
            })
        
        return logs
    
    def _get_payment_service_metrics(self, start: datetime, 
                                     end: datetime) -> List[Dict[str, Any]]:
        """Get metrics for payment service crash scenario."""
        metrics = []
        current = start
        step = timedelta(minutes=1)
        
        while current <= end:
            # Normal operation
            if (current - start).total_seconds() < 2700:  # First 45 minutes
                error_rate = 0.01
                goroutines = 50 + (current - start).total_seconds() / 60
            else:
                # Degradation starts
                error_rate = min(0.95, 0.01 + (current - start - timedelta(minutes=45)).total_seconds() / 300)
                goroutines = 50 + (current - start).total_seconds() / 10
            
            metrics.append({
                "timestamp": current.isoformat(),
                "metric": "payment_error_rate",
                "value": error_rate,
                "labels": {"service": "payment", "pod": "payment-service-7d9f8b-abc12"},
            })
            
            metrics.append({
                "timestamp": current.isoformat(),
                "metric": "goroutine_count",
                "value": goroutines,
                "labels": {"service": "payment", "pod": "payment-service-7d9f8b-abc12"},
            })
            
            current += step
        
        return metrics
    
    def _get_api_latency_metrics(self, start: datetime, 
                                 end: datetime) -> List[Dict[str, Any]]:
        """Get metrics for API latency spike scenario."""
        metrics = []
        current = start
        step = timedelta(minutes=1)
        
        while current <= end:
            # Normal latency
            if (current - start).total_seconds() < 5400:  # First 90 minutes
                p95_latency = 50
                timeout_rate = 0.001
            else:
                # Latency spike
                p95_latency = 200 + (current - start - timedelta(minutes=90)).total_seconds() / 2
                timeout_rate = min(0.40, (current - start - timedelta(minutes=90)).total_seconds() / 600)
            
            metrics.append({
                "timestamp": current.isoformat(),
                "metric": "http_request_duration_p95",
                "value": p95_latency,
                "labels": {"service": "api-gateway", "pod": "api-gateway-5c8d9a-xyz34"},
            })
            
            metrics.append({
                "timestamp": current.isoformat(),
                "metric": "http_timeout_rate",
                "value": timeout_rate,
                "labels": {"service": "api-gateway", "pod": "api-gateway-5c8d9a-xyz34"},
            })
            
            current += step
        
        return metrics
