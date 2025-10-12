# description
> [Aletheia] is a command line tool to help sysadmins or SREs to troubleshoot problems in production.

The usage should be simple and powered by one or more LLM agents 

# flow
The tool should be able to:
1. open a problem determination session
2. as the user for a description of the problem
4. fetch relevant information by date range, examples (not exhaustive) are:
   - logs from a file
   - logs from a kubernetes container inside a pod
   - logs from an Elasticsearch query to a server
   - metrics from an openmetrics query to a prometheus server
   - traces from a jaeger endpoint
5. find any hint to the code lines of the problem from the logs or traces
6. fetch the involved repositories (it can ask the user for a list of involved repos)
7. try to determine the problem in the code 


# rules
- [Aletheia] should be written in python
- The LLMs involved should be configurable for each agent with a default for every agent in case it is not configured
- Access to the external systems should be done with command line tools
- Credentials for the external system should be:
  - delegated to the tool login (e.g. kubectl with previous login)
  - stored in a hidden folder
- The credentials should be encrypted with a session key generated at session start. 
- The session key should be encrypted with a password asked to the user
- all fetched info should be stored in a hidden folder and encrypted with the session key

# Example of a session
```
$ aletheia session open --name incident-2025-10-11
> [Aletheia] Session INC-8F2A opened.
(1) Problem determination session INC-8F2A opened.
(2) Describe the problem briefly, or choose a template:
HTTP errors ↑
Latency regression
Job failures
Database errors
Other (free text)

> [User] → 1

> [Aletheia]: Problem determination started.
Enter a short description of the problem.
> [User]: Checkout API 500s since ~08:05 CEST after payments-svc v1.19 rollout.

> [Aletheia] Choose a time window:
1. Last 30m
2. Last 2h
3. Custom…

> [User] → 2

> [Aletheia] Scope signals to a system/cluster:
1. Kubernetes (prod-eu)
2. VMs (prod)
3. Serverless (eu)
4. Mixed / I’ll select per fetch

> [User] → 1

> [Aletheia] Select what to fetch first:
1. Logs: Kubernetes pods
2. Metrics: Prometheus (OpenMetrics)
3. Traces: Jaeger
4. Logs: Elasticsearch
5. Skip to code hints

> [User] → 1

> [Aletheia] Kubernetes target:
• Context: prod-eu
• Namespace: commerce
• Pod selector: app=payments-svc
• Container: app
Confirm?
1. Confirm
2. Edit

> [User] → 1

> [Aletheia] Fetching K8s logs (last 2h, sample=200)… ✅
Top error clusters:
08:05:14.921Z ERROR charge.go:112 charge failed: nil pointer dereference
08:05:14.922Z ERROR panic in chargeHandler
stack: charge.go:112 -> features.go:57 -> promo.go:88
08:05:15.004Z WARN  circuit open to promo-svc



> [Aletheia] Next fetch?
1. Metrics: Prometheus (SLOs, latency, error rate)
2. Traces: Jaeger (slow/error spans)
3. Logs: Elasticsearch (cross-service)
4. Skip to code hints

> [User] → 1

> [Aletheia] Prometheus query presets (choose any; Aletheia will overlay timelines):
[x] Error rate (5xx)
[x] p95 latency
[x] Panic count
[ ] CPU/Mem saturation
[ ] Custom…

> [User] → (accept)

> [Aletheia] Fetching metrics (last 2h)… 
Findings:
500/s: 0.2 → 7.3 at 08:05
p95 latency: 180ms → 2.4s
go_panic_total spikes at 08:05–08:12

> [Aletheia] Next fetch?
1. Traces: Jaeger
2. Logs: Elasticsearch
3. Derive code hints now

> [User] → 1

> [Aletheia] Jaeger filter:
• Service: payments-svc
• Operation: POST /v1/charges
• Min duration: 1s
1. Confirm 
2. Edit

> [User] → 1

> [Aletheia] Fetching traces… ✅
Representative span: error at chargeHandler → applyPromoIfEligible
Stack logs: features.go:57, promo.go:88

> [Aletheia] I can map stack lines to repositories. Provide or select repos:
1. git@company:commerce/payments-svc.git
2. git@company:platform/featurekit.git
3. Add another…
4. Continue without Git

> [User] → 1, 2


> [Aletheia] Fetching repos @ main and indexing symbols… 
Suggested source targets:
[x] payments-svc/internal/discounts/promo.go
[x] featurekit/features.go

Proceed to code inspection?
1. Show suspected lines
2. Full file view
3. Blame & diff around suspect lines

> [User] → 1

> [Aletheia] (snippets)
// featurekit/features.go
type Feature struct { Name string; Enabled *bool }

func IsEnabled(f *Feature) bool {
    return *f.Enabled // <-- possible nil deref (line 57)
}

// payments-svc/internal/discounts/promo.go
f := featurekit.Get("new_promo_engine") // may return nil
if featurekit.IsEnabled(f) { ... }       // nil can reach here -> panic


> [Aletheia] Probable cause (confidence: 0.86): Nil dereference in IsEnabled after lazy-load change; callers not guarding nil. Time-aligned with rollout and telemetry spikes.
Choose an immediate action:
1. Draft patch (IsEnabled nil-safe)
2. Open incident task list (alerts, tests, postmortem notes)
3. End session

> [User] → 1

> [Aletheia]
Proposed patch:
func IsEnabled(f *Feature) bool {
    return f != nil && f.Enabled != nil && *f.Enabled
}
```
