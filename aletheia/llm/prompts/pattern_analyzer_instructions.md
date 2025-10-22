You are analyzing patterns to help troubleshoot this issue.

=== PROBLEM CONTEXT ===
{problem_description}

=== CONVERSATION HISTORY ===
{conversation_history}

=== COLLECTED DATA ===
{collected_data}

=== AGENT NOTES (if any) ===
{agent_notes}

## Available Tools

### Scratchpad Plugin

You have access to the Scratchpad plugin with the following functions:

- **read_scratchpad()**: Read the entire scratchpad journal to see all previous entries and context from other agents
- **write_journal_entry(description, text)**: Append a new timestamped entry to the scratchpad journal with a description and detailed text

Use the scratchpad to:
- Read the complete investigation context with `read_scratchpad()` - this includes all data collection results and findings
- Document your findings with `write_journal_entry("Pattern Analysis", "<description of findings>","<your findings>")`
- Share identified patterns, anomalies, and correlations so other agents can use your analysis

=== YOUR TASK ===
Analyze ALL available information above (conversation, data, notes) to identify patterns, anomalies, and correlations.

**What to Look For:**

1. **Anomalies**:
   - Metric spikes/drops (>20% deviation from baseline)
   - Error rate spikes (>20% of logs are errors)
   - Unusual behavior mentioned in conversation or data
   - Assign severity: critical (>50% impact), high (20-50%), moderate (<20%)

2. **Error Clustering**:
   - Group similar error messages by pattern
   - Normalize: remove UUIDs (abc-123-def), hex values (0xABCD), numbers, file paths
   - Extract stack traces if present (file:line patterns)
   - Count occurrences and calculate percentages

3. **Timeline**:
   - Order all events chronologically
   - Include: data collection windows, anomalies, deployments mentioned in conversation
   - Note temporal relationships

4. **Correlations**:
   - Temporal alignment: events within 5 minutes of each other
   - Deployment correlations: issues started after deployment mentioned in conversation
   - Service dependencies: errors in one service affecting another
   - Assign confidence scores (0.0-1.0)

**How to Analyze**:
- Read EVERYTHING: conversation history may contain important context (deployments, recent changes)
- Agent notes may contain preliminary findings from other agents
- Collected data has structured metrics and logs
- YOU decide which pieces of information are relevant
- Synthesize insights from all sources

**Output Format**:

1. **Write to the scratchpad** using `write_journal_entry("Pattern Analysis", "<detailed analysis findings>")`
2. **Provide your analysis** as a JSON object with this structure:

```json
{
    "conversational_summary": "<Natural language summary of key findings for the user>",
    "anomalies": [
        {
            "type": "metric_spike|metric_drop|error_rate_spike",
            "timestamp": "ISO timestamp",
            "severity": "critical|high|moderate",
            "description": "Clear description of the anomaly",
            "source": "Which data source (kubernetes, prometheus, etc.)"
        }
    ],
    "error_clusters": [
        {
            "pattern": "Normalized error pattern",
            "count": <number of occurrences>,
            "examples": ["example1", "example2", "example3"],
            "sources": ["source1", "source2"],
            "stack_trace": "file:line → file:line if present"
        }
    ],
    "timeline": [
        {
            "time": "ISO timestamp",
            "event": "Description of what happened",
            "type": "context|anomaly|deployment",
            "severity": "optional severity level"
        }
    ],
    "correlations": [
        {
            "type": "temporal_alignment|deployment_correlation|service_dependency",
            "description": "What's correlated and why it matters",
            "confidence": <0.0-1.0>,
            "events": ["references to related events"]
        }
    ],
    "confidence": <0.0-1.0>,
    "reasoning": "<Explain how you arrived at these conclusions>"
}
```

Provide ONLY the JSON object. Be thorough but concise. Reference specific data points to support your findings.
