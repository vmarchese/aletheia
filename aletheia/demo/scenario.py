"""Demo scenarios with pre-defined investigation flows.

This module defines complete investigation scenarios for demo mode,
including problem descriptions, expected findings, and recommendations.
"""

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class DemoScenario:
    """A complete demo investigation scenario."""
    
    id: str
    name: str
    description: str
    service_name: str
    time_window: str
    data_sources: List[str]
    repositories: List[str]
    
    # Pre-recorded analysis results
    problem_description: str
    data_collected_summary: str
    pattern_analysis: Dict[str, Any]
    code_inspection: Dict[str, Any]
    final_diagnosis: Dict[str, Any]


# Payment Service Crash Scenario
PAYMENT_SERVICE_CRASH = DemoScenario(
    id="payment_service_crash",
    name="Payment Service Crash - Resource Deadlock",
    description="High-traffic payment service experiencing crashes due to goroutine deadlock from improper lock handling",
    service_name="payment-service",
    time_window="1h",
    data_sources=["kubernetes", "prometheus"],
    repositories=["/demo/payment-service"],
    
    problem_description="""
The payment-service pods are crashing intermittently under high load. 
Users are reporting failed payment transactions and timeout errors.
The service becomes completely unresponsive after a few minutes of normal operation.
""",
    
    data_collected_summary="""
**Kubernetes Logs** (35 entries, last 1h):
- 10 INFO: Normal payment processing
- 20 ERROR: Lock acquisition failures with "context deadline exceeded"
- 5 FATAL: Service unresponsiveness, goroutine exhaustion

**Prometheus Metrics** (60 data points, last 1h):
- payment_error_rate: Spike from 1% to 95% at T-15min
- goroutine_count: Linear growth from 50 to 500+, never decreasing
- payment_latency_p95: Increased from 50ms to 5000ms+ before crash
""",
    
    pattern_analysis={
        "anomalies": [
            {
                "type": "metric_spike",
                "severity": "critical",
                "description": "Error rate spiked from 1% to 95% in 5 minutes",
                "timestamp": "2025-10-17T14:45:00Z",
                "impact": "95% of payment requests failing",
            },
            {
                "type": "resource_leak",
                "severity": "critical",
                "description": "Goroutine count growing linearly without bounds",
                "timestamp": "2025-10-17T14:30:00Z",
                "impact": "Memory exhaustion and service crash",
            },
        ],
        "correlations": [
            {
                "source": "logs",
                "target": "metrics",
                "description": "Lock acquisition errors correlate with goroutine growth",
                "confidence": 0.95,
            },
        ],
        "error_clusters": [
            {
                "pattern": "Failed to acquire lock for payment *: context deadline exceeded",
                "count": 20,
                "percentage": 57.1,
                "first_seen": "2025-10-17T14:45:00Z",
                "severity": "error",
            },
        ],
        "timeline": [
            {"time": "14:00", "event": "Normal operation, 1% error rate"},
            {"time": "14:30", "event": "Goroutine count starts increasing abnormally"},
            {"time": "14:45", "event": "Lock acquisition errors begin"},
            {"time": "14:48", "event": "Error rate reaches 95%"},
            {"time": "14:50", "event": "Service becomes unresponsive, pods crash"},
        ],
    },
    
    code_inspection={
        "suspect_locations": [
            {
                "file": "payment.go",
                "line": 45,
                "function": "ProcessPayment",
                "issue": "Lock acquired but not released on validation error path",
                "severity": "critical",
            },
        ],
        "code_snippets": [
            {
                "file": "payment.go",
                "lines": "35-55",
                "function": "ProcessPayment",
                "code": """
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
""",
                "analysis": "The lock is acquired on line 38 but only released via defer on line 47. If validation fails on line 43, the function returns without releasing the lock, causing goroutines to block indefinitely waiting for the lock.",
            },
        ],
        "git_blame": [
            {
                "file": "payment.go",
                "line": 45,
                "author": "jane.doe@example.com",
                "commit": "a1b2c3d4",
                "date": "2025-10-15",
                "message": "feat: add concurrent payment processing",
            },
        ],
    },
    
    final_diagnosis={
        "root_cause": "Resource deadlock due to improper lock release in payment processing",
        "hypothesis": """
The payment service crashes are caused by a critical bug in the ProcessPayment function where locks are acquired but not released when validation fails. This causes goroutines to accumulate waiting for locks that will never be released, eventually exhausting system resources and crashing the service.

The bug was introduced in commit a1b2c3d4 on 2025-10-15 when concurrent payment processing was added. Under high load, multiple payments fail validation simultaneously, each leaving an unreleased lock, causing a cascading deadlock.
""",
        "confidence": 0.92,
        "evidence": [
            "Error logs show 'context deadline exceeded' for lock acquisitions",
            "Metrics show unbounded goroutine growth correlating with errors",
            "Code inspection reveals lock acquired but defer statement after validation",
            "Git blame shows recent change to add concurrent processing",
            "Timeline shows problem started exactly when high traffic began",
        ],
        "recommendations": [
            {
                "priority": "immediate",
                "action": "Apply the following patch to fix lock release ordering",
                "details": """
Move the defer statement immediately after lock acquisition:

```go
func ProcessPayment(ctx context.Context, payment *Payment) error {
    if err := acquireLock(payment.ID); err != nil {
        return fmt.Errorf("failed to acquire lock: %w", err)
    }
+   defer releaseLock(payment.ID)  // MOVED HERE - release lock on any return
    
    if err := validatePayment(payment); err != nil {
        return fmt.Errorf("validation failed: %w", err)
    }
-   defer releaseLock(payment.ID)  // REMOVED - was too late
    
    result, err := processTransaction(ctx, payment)
    if err != nil {
        return fmt.Errorf("transaction failed: %w", err)
    }
    
    return nil
}
```
""",
            },
            {
                "priority": "high",
                "action": "Add automated deadlock detection",
                "details": "Implement goroutine monitoring and alerting for unbounded growth. Alert when goroutine count exceeds threshold (e.g., 200) or grows >10/minute.",
            },
            {
                "priority": "medium",
                "action": "Add comprehensive error handling tests",
                "details": "Create unit tests that specifically test error paths to ensure resources are properly cleaned up. Use Go's race detector in CI/CD pipeline.",
            },
            {
                "priority": "low",
                "action": "Review all lock usage patterns",
                "details": "Audit all uses of acquireLock/releaseLock across the codebase to ensure consistent defer patterns immediately after acquisition.",
            },
        ],
    },
)


# API Latency Spike Scenario
API_LATENCY_SPIKE = DemoScenario(
    id="api_latency_spike",
    name="API Gateway Latency Spike - Timeout Misconfiguration",
    description="API gateway experiencing timeout errors due to aggressive timeout settings that don't account for database query complexity",
    service_name="api-gateway",
    time_window="2h",
    data_sources=["kubernetes", "prometheus"],
    repositories=["/demo/api-gateway"],
    
    problem_description="""
The API gateway is experiencing a sudden increase in timeout errors.
Users are reporting that complex queries fail with 500 errors, while simple queries work fine.
The problem started after a recent configuration update.
""",
    
    data_collected_summary="""
**Kubernetes Logs** (45 entries, last 2h):
- 15 INFO: Normal API requests (20-50ms latency)
- 30 ERROR: Request timeouts after 100ms with "context deadline exceeded"

**Prometheus Metrics** (120 data points, last 2h):
- http_request_duration_p95: Spike from 50ms to 250ms at T-30min
- http_timeout_rate: Increased from 0.1% to 40% 
- database_query_duration: Consistent at 80-150ms (within normal range)
""",
    
    pattern_analysis={
        "anomalies": [
            {
                "type": "timeout_spike",
                "severity": "high",
                "description": "Timeout rate increased from 0.1% to 40% suddenly",
                "timestamp": "2025-10-17T13:30:00Z",
                "impact": "40% of API requests timing out",
            },
        ],
        "correlations": [
            {
                "source": "timeout_errors",
                "target": "query_complexity",
                "description": "Timeouts occur only for queries taking >100ms",
                "confidence": 0.88,
            },
        ],
        "error_clusters": [
            {
                "pattern": "Request timeout after 100ms: context deadline exceeded",
                "count": 30,
                "percentage": 66.7,
                "first_seen": "2025-10-17T13:30:00Z",
                "severity": "error",
            },
        ],
        "timeline": [
            {"time": "12:00", "event": "Normal operation, <1% timeout rate"},
            {"time": "13:00", "event": "Configuration update deployed"},
            {"time": "13:30", "event": "Timeout errors start appearing"},
            {"time": "14:00", "event": "Timeout rate stabilizes at 40%"},
        ],
    },
    
    code_inspection={
        "suspect_locations": [
            {
                "file": "api.go",
                "line": 78,
                "function": "HandleAPIRequest",
                "issue": "Context timeout set to 100ms, too low for database queries",
                "severity": "high",
            },
        ],
        "code_snippets": [
            {
                "file": "api.go",
                "lines": "70-85",
                "function": "HandleAPIRequest",
                "code": """
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
""",
                "analysis": "The context timeout is hardcoded to 100ms, which is insufficient for complex database queries that can take 80-150ms. This aggressive timeout was likely intended for simple queries but doesn't account for query complexity variation.",
            },
        ],
        "git_blame": [
            {
                "file": "api.go",
                "line": 78,
                "author": "john.smith@example.com",
                "commit": "e5f6g7h8",
                "date": "2025-10-16",
                "message": "fix: update API timeout configuration",
            },
        ],
    },
    
    final_diagnosis={
        "root_cause": "Aggressive API timeout misconfiguration",
        "hypothesis": """
The API gateway timeout errors are caused by an overly aggressive 100ms timeout setting that doesn't account for the natural variance in database query execution times. Database queries typically take 80-150ms depending on complexity, making the 100ms timeout too strict.

This configuration was introduced in commit e5f6g7h8 on 2025-10-16. The timeout change was likely intended to improve responsiveness but didn't consider that many legitimate queries require >100ms to complete.
""",
        "confidence": 0.87,
        "evidence": [
            "Error logs show consistent 'context deadline exceeded after 100ms'",
            "Metrics show database queries taking 80-150ms (normal range)",
            "Timeout rate correlates with query complexity",
            "Git blame shows recent timeout configuration change",
            "Problem started immediately after configuration deployment",
        ],
        "recommendations": [
            {
                "priority": "immediate",
                "action": "Increase API timeout to accommodate database query variance",
                "details": """
Update timeout to 500ms with proper timeout handling:

```go
func HandleAPIRequest(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    
-   ctx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
+   // Increased timeout to accommodate DB query variance
+   ctx, cancel := context.WithTimeout(ctx, 500*time.Millisecond)
    defer cancel()
    
    result, err := queryDatabase(ctx, r.URL.Query())
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    
    json.NewEncoder(w).Encode(result)
}
```
""",
            },
            {
                "priority": "high",
                "action": "Implement dynamic timeout based on query complexity",
                "details": "Add query analysis to estimate required timeout based on query parameters (e.g., result set size, join complexity). Use 500ms as default, up to 2s for complex queries.",
            },
            {
                "priority": "medium",
                "action": "Add timeout monitoring and alerting",
                "details": "Implement metrics for timeout rates by query type. Alert when timeout rate exceeds 5% for any query pattern.",
            },
            {
                "priority": "low",
                "action": "Optimize slow database queries",
                "details": "Profile queries taking >150ms and add appropriate indexes or query optimization. Target p95 latency <100ms for all queries.",
            },
        ],
    },
)


# Registry of all demo scenarios
DEMO_SCENARIOS: Dict[str, DemoScenario] = {
    "payment_service_crash": PAYMENT_SERVICE_CRASH,
    "api_latency_spike": API_LATENCY_SPIKE,
}
