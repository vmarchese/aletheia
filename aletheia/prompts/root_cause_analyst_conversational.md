You are synthesizing all findings to generate a comprehensive root cause diagnosis.

=== PROBLEM CONTEXT ===
{problem_description}

=== CONVERSATION HISTORY ===
{conversation_history}

=== COLLECTED DATA ===
{collected_data}

=== PATTERN ANALYSIS ===
{pattern_analysis}

=== CODE INSPECTION ===
{code_inspection}

=== AGENT NOTES (if any) ===
{agent_notes}

=== YOUR TASK ===
Synthesize ALL information above to generate a comprehensive root cause diagnosis.

**Evidence Synthesis:**
1. Extract key evidence from all sections above (YOU decide what's most relevant)
2. Weight evidence based on:
   - Severity (critical > high > medium > low)
   - Reliability (code-level > metrics > logs > conversation mentions)
   - Correlation strength (how well do pieces of evidence align?)
3. Build a list of evidence items sorted by weight (highest first)

**Causal Chain:**
1. Order events chronologically to show how the problem developed
2. Include: context from conversation, deployment events, anomalies, errors, code issues
3. Show cause-and-effect relationships

**Root Cause Hypothesis:**
1. Identify the root cause type (e.g., nil_pointer_dereference, index_out_of_bounds, timeout, memory_issue, configuration_error)
2. Provide detailed description based on strongest evidence
3. Identify location (file:line if code evidence available, otherwise service/component name)
4. Base hypothesis on the evidence with highest weight

**Confidence Calculation (0.0-1.0):**
Consider:
- Evidence quality: Average weight of top evidence items
- Evidence quantity: More evidence = higher confidence (normalize by count, max at 10 items)
- Data completeness: Do we have data from multiple sources? Pattern analysis? Code inspection?
- Consistency: Do all pieces of evidence point to the same conclusion?
- Code evidence bonus: +0.1 if we have code-level evidence
- Correlation strength: If there are deployment or temporal correlations

**Recommendations (Prioritized):**
- **Immediate**: Rollback if deployment correlation detected AND confidence > 0.5
- **High**: Code fixes for identified bugs (nil checks, bounds checking, error handling)
- **Medium**: Add unit tests, monitoring alerts
- **Low**: Code reviews for similar patterns, preventive improvements

Each recommendation should have:
- priority: immediate|high|medium|low
- action: Specific action to take
- rationale: Why this action is recommended
- type: rollback|code_fix|testing|monitoring|code_review
- location: file:line if applicable

**Timeline Correlation:**
- deployment_mentioned: true if deployment mentioned in problem/conversation
- first_error_time: ISO timestamp of first error from timeline (or null)
- alignment: Description of temporal alignment between deployment and errors (or null)

**Output Format:**
Provide your diagnosis as a JSON object with this structure:
{{
  "conversational_summary": "<Natural language summary for the user explaining the root cause and key findings>",
  "root_cause": {{
    "type": "<root_cause_type>",
    "confidence": <0.0-1.0>,
    "description": "<detailed description>",
    "location": "<file:line or service name>"
  }},
  "evidence": [
    {{
      "type": "anomaly|error_cluster|correlation|code_issue",
      "source": "pattern_analysis|code_inspection|conversation",
      "severity": "critical|high|medium|low",
      "description": "<evidence description>",
      "weight": <0.0-1.0>
    }}
  ],
  "timeline_correlation": {{
    "deployment_mentioned": true|false,
    "first_error_time": "<ISO timestamp or null>",
    "alignment": "<description or null>"
  }},
  "recommended_actions": [
    {{
      "priority": "immediate|high|medium|low",
      "action": "<action description>",
      "rationale": "<why this action>",
      "type": "rollback|code_fix|testing|monitoring|code_review",
      "location": "<file:line if applicable>"
    }}
  ],
  "confidence_breakdown": {{
    "evidence_quality": <0.0-1.0>,
    "data_completeness": <0.0-1.0>,
    "consistency": <0.0-1.0>,
    "reasoning": "<explain how you calculated confidence>"
  }}
}}

Provide ONLY the JSON object. Be thorough, synthesize from ALL sources, and be honest about uncertainty.
