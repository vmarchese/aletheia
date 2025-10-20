Understand the user's intent from their message in the context of a troubleshooting investigation.

User Message: {user_message}

Conversation History:
{conversation_history}

Current Investigation State:
{investigation_state}

Classify the user's intent into ONE of these categories:
- fetch_data: User wants to collect logs, metrics, or traces
- analyze_patterns: User wants to analyze patterns in collected data
- inspect_code: User wants to inspect source code related to errors
- diagnose: User wants root cause analysis or diagnosis
- show_findings: User wants to see current findings or results
- clarify: User is asking questions or needs clarification
- modify_scope: User wants to change the investigation scope (time window, services, etc.)
- other: Intent doesn't match any category

Extract parameters if mentioned (BE PRECISE about Kubernetes terms):
- pod: Pod name if mentioned (e.g., "pod bonifico-9999", "check payments-svc pod")
  IMPORTANT: If user says "pod X", extract X as "pod" not "services"
- namespace: Kubernetes namespace (e.g., "payment namespace", "in production", "staging")
  Common patterns: "in <namespace>", "<namespace> namespace", "on <namespace>"
- container: Container name within a pod if specified
- services: Service/application names (NOT pod names - pods usually have random suffixes)
- time_window: Time window mentioned (e.g., "2h", "last hour", "since 10am")
- data_sources: Specific data sources mentioned (kubernetes, prometheus, elasticsearch)
- keywords: Important keywords or error messages mentioned

Examples of extraction:
- "check pod payments-abc123 in production" → pod="payments-abc123", namespace="production"
- "logs from bonifico-9999 in payment namespace" → pod="bonifico-9999", namespace="payment"
- "the payments service" → services=["payments"] (no pod specified)
- "pod kube-proxy-c7mjh" → pod="kube-proxy-c7mjh" (NOT a service)

Respond ONLY with a JSON object in this exact format:
{{
  "intent": "<intent_category>",
  "confidence": <0.0-1.0>,
  "parameters": {{
    "pod": "pod-name-if-mentioned",
    "namespace": "namespace-if-mentioned",
    "container": "container-if-mentioned",
    "services": ["service1", "service2"],
    "time_window": "2h",
    "data_sources": ["kubernetes"],
    "keywords": ["error", "timeout"]
  }},
  "reasoning": "<brief explanation of your classification>"
}}
