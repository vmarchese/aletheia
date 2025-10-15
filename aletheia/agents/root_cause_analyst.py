"""Root Cause Analyst Agent for synthesizing findings and generating diagnosis.

This agent is responsible for:
- Reading entire scratchpad (all sections)
- Synthesizing findings from all previous agents
- Correlating evidence across sections
- Identifying causal chains
- Generating root cause hypothesis
- Calculating confidence score
- Generating prioritized recommendations
- Writing results to the scratchpad's FINAL_DIAGNOSIS section

This is the SK-based version that uses Semantic Kernel's ChatCompletionAgent
for root cause analysis with maintained synthesis and recommendation methods.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import re
import json

from aletheia.agents.sk_base import SKBaseAgent
from aletheia.llm.prompts import compose_messages, get_system_prompt, get_user_prompt_template
from aletheia.scratchpad import ScratchpadSection


class RootCauseAnalystAgent(SKBaseAgent):
    """SK-based agent responsible for generating the final root cause diagnosis.
    
    This agent uses Semantic Kernel's ChatCompletionAgent with analytical
    helper functions for evidence synthesis and recommendation generation.
    
    The Root Cause Analyst Agent:
    1. Reads the entire scratchpad (all sections)
    2. Synthesizes findings from all agents
    3. Identifies causal chains and correlations
    4. Generates root cause hypothesis
    5. Calculates confidence score (0.0-1.0)
    6. Generates prioritized recommendations
    7. Writes results to the FINAL_DIAGNOSIS section
    
    Attributes:
        config: Agent configuration including LLM settings
        scratchpad: Scratchpad for reading data and writing diagnosis
        use_sk: Whether to use SK agent for analysis (default: False for compatibility)
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad: Any, use_sk: bool = False):
        """Initialize the SK-based Root Cause Analyst Agent.
        
        Args:
            config: Configuration dictionary with LLM settings
            scratchpad: Scratchpad instance for agent communication
            use_sk: Whether to use SK agent for root cause analysis (default: False)
        """
        super().__init__(config, scratchpad, agent_name="root_cause_analyst")
        self.use_sk = use_sk
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the root cause analysis process.
        
        Supports both SK-based and direct analysis modes. SK mode uses the
        ChatCompletionAgent for analysis (future), while direct mode uses
        the analytical helper methods (current default).
        
        Args:
            **kwargs: Additional parameters for analysis
                - use_sk: Optional override for SK mode
        
        Returns:
            Dictionary with execution results:
                - success: bool - Whether execution succeeded
                - confidence: float - Confidence score (0.0-1.0)
                - recommendations_count: int - Number of recommendations
                - root_cause_type: str - Type of root cause identified
        
        Raises:
            ValueError: If required scratchpad sections are missing
        """
        # Allow per-call override of SK mode
        use_sk = kwargs.get("use_sk", self.use_sk)
        
        if use_sk:
            return self._execute_with_sk(**kwargs)
        else:
            return self._execute_direct(**kwargs)
    
    def _execute_direct(self, **kwargs) -> Dict[str, Any]:
        """Execute root cause analysis using direct analytical methods (original implementation).
        
        This is the original implementation that uses helper methods for analysis.
        Maintains full backward compatibility.
        
        Args:
            **kwargs: Additional parameters for analysis
        
        Returns:
            Dictionary with execution results
        
        Raises:
            ValueError: If required scratchpad sections are missing
        """
        # Read all scratchpad sections
        problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION)
        data_collected = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED)
        pattern_analysis = self.read_scratchpad(ScratchpadSection.PATTERN_ANALYSIS)
        code_inspection = self.read_scratchpad(ScratchpadSection.CODE_INSPECTION)
        
        # Validate required sections
        if not problem:
            raise ValueError("PROBLEM_DESCRIPTION section is missing")
        if not data_collected:
            raise ValueError("DATA_COLLECTED section is missing")
        if not pattern_analysis:
            raise ValueError("PATTERN_ANALYSIS section is missing")
        
        # Code inspection is optional (may not be available)
        
        # Synthesize all findings
        synthesis = self.synthesize_findings(
            problem=problem,
            data_collected=data_collected,
            pattern_analysis=pattern_analysis,
            code_inspection=code_inspection
        )
        
        # Generate root cause hypothesis
        hypothesis = self.generate_hypothesis(synthesis)
        
        # Calculate confidence score
        confidence = self.calculate_confidence(synthesis)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(
            hypothesis=hypothesis,
            synthesis=synthesis,
            confidence=confidence
        )
        
        # Build final diagnosis
        diagnosis = {
            "root_cause": {
                "type": hypothesis.get("type", "unknown"),
                "confidence": confidence,
                "description": hypothesis.get("description", ""),
                "location": hypothesis.get("location", "")
            },
            "evidence": synthesis.get("key_evidence", []),
            "timeline_correlation": synthesis.get("timeline_correlation", {}),
            "recommended_actions": recommendations
        }
        
        # Write diagnosis to scratchpad
        self.write_scratchpad(ScratchpadSection.FINAL_DIAGNOSIS, diagnosis)
        
        return {
            "success": True,
            "confidence": confidence,
            "recommendations_count": len(recommendations),
            "root_cause_type": hypothesis.get("type", "unknown")
        }
    
    def _execute_with_sk(self, **kwargs) -> Dict[str, Any]:
        """Execute root cause analysis using SK ChatCompletionAgent.
        
        This method uses the SK agent to perform root cause analysis. It builds
        a comprehensive prompt with all scratchpad sections and asks the SK agent
        to synthesize findings and generate a diagnosis, then parses the response.
        
        Falls back to direct mode if SK fails.
        
        Args:
            **kwargs: Additional parameters for analysis
        
        Returns:
            Dictionary with execution results
        
        Raises:
            ValueError: If required scratchpad sections are missing
        """
        try:
            # Read all scratchpad sections
            problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION)
            data_collected = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED)
            pattern_analysis = self.read_scratchpad(ScratchpadSection.PATTERN_ANALYSIS)
            code_inspection = self.read_scratchpad(ScratchpadSection.CODE_INSPECTION)
            
            # Validate required sections
            if not problem:
                raise ValueError("PROBLEM_DESCRIPTION section is missing")
            if not data_collected:
                raise ValueError("DATA_COLLECTED section is missing")
            if not pattern_analysis:
                raise ValueError("PATTERN_ANALYSIS section is missing")
            
            # Build SK prompt for root cause analysis
            prompt = self._build_sk_synthesis_prompt(
                problem=problem,
                data_collected=data_collected,
                pattern_analysis=pattern_analysis,
                code_inspection=code_inspection
            )
            
            # Invoke SK agent
            response = self.invoke(prompt)
            
            # Parse SK response
            diagnosis = self._parse_sk_diagnosis_response(response)
            
            # Write diagnosis to scratchpad
            self.write_scratchpad(ScratchpadSection.FINAL_DIAGNOSIS, diagnosis)
            
            # Return execution results
            return {
                "success": True,
                "confidence": diagnosis.get("root_cause", {}).get("confidence", 0.0),
                "recommendations_count": len(diagnosis.get("recommended_actions", [])),
                "root_cause_type": diagnosis.get("root_cause", {}).get("type", "unknown")
            }
        
        except Exception as e:
            # Fall back to direct mode on SK failure
            print(f"SK analysis failed ({str(e)}), falling back to direct mode")
            return self._execute_direct(**kwargs)
    
    def _build_sk_synthesis_prompt(
        self,
        problem: Dict[str, Any],
        data_collected: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
        code_inspection: Optional[Dict[str, Any]]
    ) -> str:
        """Build comprehensive prompt for SK agent root cause synthesis.
        
        Args:
            problem: Problem description from PROBLEM_DESCRIPTION section
            data_collected: Collected data from DATA_COLLECTED section
            pattern_analysis: Pattern analysis from PATTERN_ANALYSIS section
            code_inspection: Code inspection from CODE_INSPECTION section (optional)
        
        Returns:
            Formatted prompt string for SK agent
        """
        prompt = f"""Synthesize all findings and generate a comprehensive root cause diagnosis.

Problem Description:
{json.dumps(problem, indent=2)}

Data Collected:
{json.dumps(data_collected, indent=2)}

Pattern Analysis:
{json.dumps(pattern_analysis, indent=2)}
"""
        
        if code_inspection:
            prompt += f"""
Code Inspection:
{json.dumps(code_inspection, indent=2)}
"""
        
        prompt += """

Please perform the following root cause analysis:

1. **Evidence Synthesis**: Identify and weight key evidence:
   - Extract evidence from anomalies, error clusters, correlations
   - Extract code issues (if available)
   - Assign weights based on severity and reliability
   - Sort by weight (highest first)

2. **Causal Chain Building**: Construct timeline of events:
   - Order events chronologically
   - Identify cause-and-effect relationships
   - Link deployment events to errors/anomalies

3. **Root Cause Hypothesis**: Generate hypothesis:
   - Identify root cause type (nil_pointer_dereference, index_out_of_bounds, etc.)
   - Provide detailed description
   - Identify location (file:line if available)
   - Base on strongest evidence

4. **Confidence Scoring**: Calculate confidence (0.0-1.0):
   - Evidence quality and quantity
   - Data completeness
   - Consistency across evidence
   - Presence of code-level evidence
   - Correlation strength

5. **Recommendations**: Generate prioritized actions:
   - Immediate: Critical actions (rollback if deployment correlation)
   - High: Code fixes based on evidence
   - Medium: Testing and monitoring improvements
   - Low: Preventive code reviews

Return your analysis as a JSON object with this structure:
{{
  "root_cause": {{
    "type": "root_cause_type",
    "confidence": 0.0-1.0,
    "description": "detailed description",
    "location": "file:line or service name"
  }},
  "evidence": [
    {{
      "type": "anomaly|error_cluster|correlation|code_issue",
      "source": "pattern_analysis|code_inspection",
      "severity": "critical|high|medium|low",
      "description": "evidence description",
      "weight": 0.0-1.0
    }}
  ],
  "timeline_correlation": {{
    "deployment_mentioned": true|false,
    "first_error_time": "ISO timestamp or null",
    "alignment": "description of temporal alignment or null"
  }},
  "recommended_actions": [
    {{
      "priority": "immediate|high|medium|low",
      "action": "action description",
      "rationale": "why this action is recommended",
      "type": "rollback|code_fix|testing|monitoring|code_review",
      "location": "file:line if applicable"
    }}
  ]
}}

Ensure all JSON is valid and properly formatted."""
        
        return prompt
    
    def _parse_sk_diagnosis_response(self, response: str) -> Dict[str, Any]:
        """Parse SK agent response to extract diagnosis.
        
        Args:
            response: Response from SK agent
        
        Returns:
            Parsed diagnosis dictionary
        
        Raises:
            ValueError: If response cannot be parsed
        """
        # Try to extract JSON from response
        try:
            # Look for JSON block in response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                diagnosis = json.loads(json_match.group(0))
                return diagnosis
            else:
                # No JSON found, try to parse entire response
                diagnosis = json.loads(response)
                return diagnosis
        except json.JSONDecodeError as e:
            # Fallback: construct diagnosis from response text
            return {
                "root_cause": {
                    "type": "unknown",
                    "confidence": 0.5,
                    "description": response[:500],  # First 500 chars
                    "location": "unknown"
                },
                "evidence": [],
                "timeline_correlation": {
                    "deployment_mentioned": False,
                    "first_error_time": None,
                    "alignment": None
                },
                "recommended_actions": []
            }
    
    def synthesize_findings(
        self,
        problem: Dict[str, Any],
        data_collected: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
        code_inspection: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Synthesize findings from all agents.
        
        Args:
            problem: Problem description from scratchpad
            data_collected: Collected data from scratchpad
            pattern_analysis: Pattern analysis from scratchpad
            code_inspection: Code inspection from scratchpad (optional)
        
        Returns:
            Dictionary with synthesized findings:
                - key_evidence: List of key evidence items
                - causal_chain: List of causal events
                - data_completeness: Score 0.0-1.0
                - consistency: Score 0.0-1.0
                - timeline_correlation: Timeline correlation info
        """
        synthesis = {
            "key_evidence": [],
            "causal_chain": [],
            "data_completeness": 0.0,
            "consistency": 0.0,
            "timeline_correlation": {}
        }
        
        # Collect key evidence
        evidence = []
        
        # Evidence from anomalies
        anomalies = pattern_analysis.get("anomalies", [])
        for anomaly in anomalies:
            evidence.append({
                "type": "anomaly",
                "source": "pattern_analysis",
                "severity": anomaly.get("severity", "unknown"),
                "description": f"{anomaly.get('type', 'unknown')}: {anomaly.get('description', '')}",
                "weight": self._calculate_evidence_weight(anomaly, "anomaly")
            })
        
        # Evidence from error clusters
        error_clusters = pattern_analysis.get("error_clusters", [])
        if error_clusters:
            # Most common error cluster
            top_cluster = error_clusters[0] if error_clusters else None
            if top_cluster:
                evidence.append({
                    "type": "error_cluster",
                    "source": "pattern_analysis",
                    "severity": "high" if top_cluster.get("count", 0) > 10 else "medium",
                    "description": f"Error pattern: {top_cluster.get('pattern', 'unknown')} ({top_cluster.get('count', 0)} occurrences)",
                    "weight": self._calculate_evidence_weight(top_cluster, "error_cluster")
                })
        
        # Evidence from correlations
        correlations = pattern_analysis.get("correlations", [])
        for correlation in correlations:
            evidence.append({
                "type": "correlation",
                "source": "pattern_analysis",
                "severity": "high",
                "description": correlation.get("description", ""),
                "confidence": correlation.get("confidence", 0.0),
                "weight": correlation.get("confidence", 0.5)
            })
        
        # Evidence from code inspection (if available)
        if code_inspection:
            suspect_files = code_inspection.get("suspect_files", [])
            for suspect_file in suspect_files[:3]:  # Top 3 suspects
                evidence.append({
                    "type": "code_issue",
                    "source": "code_inspection",
                    "severity": "high",
                    "description": f"Issue in {suspect_file.get('file', 'unknown')}:{suspect_file.get('line', 0)} - {suspect_file.get('analysis', '')}",
                    "git_blame": suspect_file.get("git_blame", {}),
                    "weight": self._calculate_evidence_weight(suspect_file, "code_issue")
                })
        
        # Sort evidence by weight (highest first)
        evidence.sort(key=lambda x: x.get("weight", 0), reverse=True)
        synthesis["key_evidence"] = evidence
        
        # Build causal chain
        causal_chain = self._build_causal_chain(
            problem=problem,
            pattern_analysis=pattern_analysis,
            code_inspection=code_inspection,
            evidence=evidence
        )
        synthesis["causal_chain"] = causal_chain
        
        # Calculate data completeness
        completeness = self._calculate_data_completeness(
            data_collected=data_collected,
            pattern_analysis=pattern_analysis,
            code_inspection=code_inspection
        )
        synthesis["data_completeness"] = completeness
        
        # Calculate consistency
        consistency = self._calculate_consistency(evidence, causal_chain)
        synthesis["consistency"] = consistency
        
        # Extract timeline correlation
        timeline_correlation = self._extract_timeline_correlation(
            problem=problem,
            pattern_analysis=pattern_analysis
        )
        synthesis["timeline_correlation"] = timeline_correlation
        
        return synthesis
    
    def generate_hypothesis(self, synthesis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate root cause hypothesis from synthesis.
        
        Args:
            synthesis: Synthesized findings
        
        Returns:
            Dictionary with hypothesis:
                - type: Root cause type
                - description: Detailed description
                - location: File/service location
        """
        # Get top evidence items
        evidence = synthesis.get("key_evidence", [])
        causal_chain = synthesis.get("causal_chain", [])
        
        if not evidence:
            return {
                "type": "unknown",
                "description": "Insufficient evidence to determine root cause",
                "location": "unknown"
            }
        
        # Use LLM to generate hypothesis from evidence
        try:
            llm = self.get_llm()
            
            # Get user prompt template
            prompt_template = get_user_prompt_template("root_cause_analyst_synthesis")
            
            # Format evidence for LLM
            evidence_str = "\n".join([
                f"- [{e.get('severity', 'unknown')}] {e.get('description', '')}"
                for e in evidence[:10]  # Top 10 pieces of evidence
            ])
            
            # Format causal chain
            causal_chain_str = "\n".join([
                f"{i+1}. {event.get('description', '')}"
                for i, event in enumerate(causal_chain)
            ])
            
            # Format user prompt
            user_prompt = prompt_template.format(
                problem_description=synthesis.get("problem_description", "Unknown problem"),
                evidence=evidence_str or "No evidence available",
                causal_chain=causal_chain_str or "No causal chain identified",
                data_completeness=f"{synthesis.get('data_completeness', 0) * 100:.1f}%",
                consistency=f"{synthesis.get('consistency', 0) * 100:.1f}%"
            )
            
            # Get system prompt
            system_prompt = get_system_prompt("root_cause_analyst")
            
            # Compose messages
            messages = compose_messages(system_prompt, user_prompt)
            
            # Get LLM analysis
            response = llm.complete(
                prompt=messages[-1]["content"] if messages else user_prompt,
                system_prompt=messages[0]["content"] if len(messages) > 1 else system_prompt,
                temperature=0.2,  # Low temperature for focused analysis
                max_tokens=1000
            )
            
            # Parse LLM response to extract hypothesis components
            hypothesis = self._parse_llm_hypothesis(response, evidence)
            
            return hypothesis
        
        except Exception as e:
            # Fallback to heuristic-based hypothesis
            return self._generate_heuristic_hypothesis(evidence, causal_chain)
    
    def calculate_confidence(self, synthesis: Dict[str, Any]) -> float:
        """Calculate confidence score for the diagnosis.
        
        Args:
            synthesis: Synthesized findings
        
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Factors that contribute to confidence:
        # 1. Number and quality of evidence items
        # 2. Data completeness
        # 3. Consistency across evidence
        # 4. Presence of code-level evidence
        # 5. Correlation strength
        
        scores = []
        
        # Evidence quality score (0.0-1.0)
        evidence = synthesis.get("key_evidence", [])
        if evidence:
            # Weight by evidence weight and count
            evidence_weights = [e.get("weight", 0) for e in evidence]
            avg_weight = sum(evidence_weights) / len(evidence_weights) if evidence_weights else 0
            # Normalize by count (more evidence = higher confidence, capped at 10)
            count_factor = min(len(evidence) / 10, 1.0)
            evidence_score = avg_weight * 0.7 + count_factor * 0.3
            scores.append(evidence_score)
        else:
            scores.append(0.0)
        
        # Data completeness score
        completeness = synthesis.get("data_completeness", 0.0)
        scores.append(completeness)
        
        # Consistency score
        consistency = synthesis.get("consistency", 0.0)
        scores.append(consistency)
        
        # Code evidence bonus (presence of code inspection adds confidence)
        has_code_evidence = any(e.get("type") == "code_issue" for e in evidence)
        code_bonus = 0.1 if has_code_evidence else 0.0
        
        # Correlation strength (if available)
        correlations = [e for e in evidence if e.get("type") == "correlation"]
        if correlations:
            max_correlation_conf = max(c.get("confidence", 0) for c in correlations)
            scores.append(max_correlation_conf)
        
        # Calculate weighted average
        base_confidence = sum(scores) / len(scores) if scores else 0.0
        
        # Apply code bonus
        final_confidence = min(base_confidence + code_bonus, 1.0)
        
        # Round to 2 decimal places
        return round(final_confidence, 2)
    
    def generate_recommendations(
        self,
        hypothesis: Dict[str, Any],
        synthesis: Dict[str, Any],
        confidence: float
    ) -> List[Dict[str, Any]]:
        """Generate prioritized recommendations.
        
        Args:
            hypothesis: Root cause hypothesis
            synthesis: Synthesized findings
            confidence: Confidence score
        
        Returns:
            List of recommendation dictionaries with priority, action, rationale
        """
        recommendations = []
        
        # Immediate actions (always include if confidence > 0.5)
        if confidence > 0.5:
            # Check for deployment correlation
            timeline_corr = synthesis.get("timeline_correlation", {})
            if timeline_corr.get("deployment_mentioned"):
                recommendations.append({
                    "priority": "immediate",
                    "action": f"Consider rollback to previous version",
                    "rationale": "Error spike correlates with recent deployment",
                    "type": "rollback"
                })
        
        # High priority actions (code fixes)
        evidence = synthesis.get("key_evidence", [])
        code_issues = [e for e in evidence if e.get("type") == "code_issue"]
        
        if code_issues:
            top_issue = code_issues[0]
            description = top_issue.get("description", "")
            
            # Generate patch recommendation
            if "nil pointer" in description.lower() or "null pointer" in description.lower():
                recommendations.append({
                    "priority": "high",
                    "action": "Apply nil-safety check",
                    "rationale": "Prevent nil/null pointer dereference",
                    "type": "code_fix",
                    "location": self._extract_location_from_description(description)
                })
            elif "index out of bounds" in description.lower():
                recommendations.append({
                    "priority": "high",
                    "action": "Add bounds checking",
                    "rationale": "Prevent array/slice index errors",
                    "type": "code_fix",
                    "location": self._extract_location_from_description(description)
                })
            else:
                recommendations.append({
                    "priority": "high",
                    "action": f"Review and fix code issue",
                    "rationale": description,
                    "type": "code_fix",
                    "location": self._extract_location_from_description(description)
                })
        
        # Medium priority actions (testing and monitoring)
        if code_issues:
            recommendations.append({
                "priority": "medium",
                "action": "Add unit tests for error scenario",
                "rationale": "Prevent regression of this issue",
                "type": "testing"
            })
        
        # Check for error rate spikes or anomalies
        anomalies = [e for e in evidence if e.get("type") == "anomaly"]
        if anomalies:
            recommendations.append({
                "priority": "medium",
                "action": "Add monitoring alert for error rate threshold",
                "rationale": "Early detection of similar issues",
                "type": "monitoring"
            })
        
        # Low priority actions (review and improvements)
        if code_issues:
            recommendations.append({
                "priority": "low",
                "action": "Review similar code patterns in codebase",
                "rationale": "Identify and fix similar issues proactively",
                "type": "code_review"
            })
        
        # Sort by priority
        priority_order = {"immediate": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))
        
        return recommendations
    
    # Helper methods
    
    def _calculate_evidence_weight(self, evidence: Dict[str, Any], evidence_type: str) -> float:
        """Calculate weight of evidence item.
        
        Args:
            evidence: Evidence dictionary
            evidence_type: Type of evidence (anomaly, error_cluster, code_issue)
        
        Returns:
            Weight between 0.0 and 1.0
        """
        if evidence_type == "anomaly":
            severity = evidence.get("severity", "unknown")
            severity_weights = {"critical": 1.0, "high": 0.8, "medium": 0.6, "low": 0.4}
            return severity_weights.get(severity, 0.5)
        
        elif evidence_type == "error_cluster":
            # Weight by frequency
            count = evidence.get("count", 0)
            # Normalize: >100 errors = 1.0, <10 errors = 0.3
            normalized = min((count - 10) / 90, 1.0) if count >= 10 else count / 10 * 0.3
            return max(0.3, min(normalized, 1.0))
        
        elif evidence_type == "code_issue":
            # Code-level evidence is high weight
            # Higher weight if git blame is recent
            git_blame = evidence.get("git_blame", {})
            if git_blame and "date" in git_blame:
                # Recent changes (< 7 days) get higher weight
                try:
                    date_str = git_blame["date"]
                    # Simple heuristic: if date string contains "days ago" or recent year
                    if "2025" in date_str or "2024" in date_str:
                        return 0.9
                except:
                    pass
            return 0.8
        
        return 0.5
    
    def _build_causal_chain(
        self,
        problem: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
        code_inspection: Optional[Dict[str, Any]],
        evidence: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build causal chain of events.
        
        Args:
            problem: Problem description
            pattern_analysis: Pattern analysis data
            code_inspection: Code inspection data (optional)
            evidence: List of evidence items
        
        Returns:
            List of causal event dictionaries
        """
        chain = []
        
        # Extract timeline events
        timeline = pattern_analysis.get("timeline", [])
        
        # Sort by timestamp if available
        sorted_timeline = sorted(timeline, key=lambda x: x.get("time", ""))
        
        # Build chain from timeline
        for i, event in enumerate(sorted_timeline):
            chain.append({
                "step": i + 1,
                "description": event.get("event", "Unknown event"),
                "timestamp": event.get("time", ""),
                "type": event.get("type", "unknown")
            })
        
        # Add code issue as potential root if available
        if code_inspection:
            suspect_files = code_inspection.get("suspect_files", [])
            if suspect_files:
                chain.append({
                    "step": len(chain) + 1,
                    "description": f"Root cause: {suspect_files[0].get('file', 'unknown')}:{suspect_files[0].get('line', 0)}",
                    "timestamp": "",
                    "type": "root_cause"
                })
        
        return chain
    
    def _calculate_data_completeness(
        self,
        data_collected: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
        code_inspection: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate data completeness score.
        
        Args:
            data_collected: Collected data
            pattern_analysis: Pattern analysis
            code_inspection: Code inspection (optional)
        
        Returns:
            Completeness score between 0.0 and 1.0
        """
        completeness_factors = []
        
        # Check if we have data from multiple sources
        data_sources = len(data_collected) if data_collected else 0
        completeness_factors.append(min(data_sources / 2, 1.0))  # Ideal: 2+ sources
        
        # Check if we have anomalies
        has_anomalies = len(pattern_analysis.get("anomalies", [])) > 0
        completeness_factors.append(1.0 if has_anomalies else 0.5)
        
        # Check if we have error clusters
        has_clusters = len(pattern_analysis.get("error_clusters", [])) > 0
        completeness_factors.append(1.0 if has_clusters else 0.7)
        
        # Check if we have code inspection
        has_code = code_inspection is not None and len(code_inspection.get("suspect_files", [])) > 0
        completeness_factors.append(1.0 if has_code else 0.6)
        
        # Average
        return sum(completeness_factors) / len(completeness_factors)
    
    def _calculate_consistency(
        self,
        evidence: List[Dict[str, Any]],
        causal_chain: List[Dict[str, Any]]
    ) -> float:
        """Calculate consistency across evidence.
        
        Args:
            evidence: List of evidence items
            causal_chain: Causal chain of events
        
        Returns:
            Consistency score between 0.0 and 1.0
        """
        if not evidence:
            return 0.0
        
        # Check if evidence points to similar issues
        # Group evidence by type
        evidence_types = {}
        for e in evidence:
            etype = e.get("type", "unknown")
            if etype not in evidence_types:
                evidence_types[etype] = []
            evidence_types[etype].append(e)
        
        # More concentrated evidence types = higher consistency
        if len(evidence_types) == 1:
            consistency = 1.0
        elif len(evidence_types) <= 3:
            consistency = 0.8
        else:
            consistency = 0.6
        
        # Boost consistency if we have a clear causal chain
        if len(causal_chain) >= 3:
            consistency += 0.1
        
        return min(consistency, 1.0)
    
    def _extract_timeline_correlation(
        self,
        problem: Dict[str, Any],
        pattern_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract timeline correlation information.
        
        Args:
            problem: Problem description
            pattern_analysis: Pattern analysis data
        
        Returns:
            Dictionary with timeline correlation info
        """
        correlation = {
            "deployment_mentioned": False,
            "first_error_time": None,
            "alignment": None
        }
        
        # Check if deployment is mentioned in problem
        description = problem.get("description", "")
        if "deploy" in description.lower() or "rollout" in description.lower():
            correlation["deployment_mentioned"] = True
        
        # Get first error time from timeline
        timeline = pattern_analysis.get("timeline", [])
        if timeline:
            # Find first anomaly/error event
            for event in timeline:
                if event.get("type") in ["anomaly", "error"]:
                    correlation["first_error_time"] = event.get("time", "")
                    break
        
        # Check correlations for temporal alignment
        correlations = pattern_analysis.get("correlations", [])
        for corr in correlations:
            if "temporal" in corr.get("type", "").lower():
                correlation["alignment"] = corr.get("description", "")
                break
        
        return correlation
    
    def _parse_llm_hypothesis(
        self,
        llm_response: str,
        evidence: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parse LLM response to extract hypothesis.
        
        Args:
            llm_response: Response from LLM
            evidence: Evidence list for fallback
        
        Returns:
            Hypothesis dictionary
        """
        # Try to extract structured information from LLM response
        hypothesis = {
            "type": "unknown",
            "description": llm_response,
            "location": "unknown"
        }
        
        # Extract type (look for common root cause types)
        type_patterns = [
            (r"nil pointer|null pointer|null reference", "nil_pointer_dereference"),
            (r"index out of bounds|array.*bounds", "index_out_of_bounds"),
            (r"deadlock|race condition", "concurrency_issue"),
            (r"memory leak|out of memory", "memory_issue"),
            (r"connection.*timeout|timeout", "timeout"),
            (r"authentication|authorization", "auth_issue"),
            (r"configuration|config|misconfiguration", "configuration_error"),
        ]
        
        for pattern, rca_type in type_patterns:
            if re.search(pattern, llm_response, re.IGNORECASE):
                hypothesis["type"] = rca_type
                break
        
        # Extract location (file:line pattern)
        location_match = re.search(r'([\w/]+\.\w+):(\d+)', llm_response)
        if location_match:
            hypothesis["location"] = location_match.group(0)
        else:
            # Fallback to evidence location
            code_evidence = [e for e in evidence if e.get("type") == "code_issue"]
            if code_evidence:
                desc = code_evidence[0].get("description", "")
                loc_match = re.search(r'([\w/]+\.\w+):(\d+)', desc)
                if loc_match:
                    hypothesis["location"] = loc_match.group(0)
        
        return hypothesis
    
    def _generate_heuristic_hypothesis(
        self,
        evidence: List[Dict[str, Any]],
        causal_chain: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate hypothesis using heuristics (fallback when LLM fails).
        
        Args:
            evidence: List of evidence items
            causal_chain: Causal chain of events
        
        Returns:
            Hypothesis dictionary
        """
        if not evidence:
            return {
                "type": "unknown",
                "description": "Insufficient evidence to determine root cause",
                "location": "unknown"
            }
        
        # Use top evidence item
        top_evidence = evidence[0]
        description = top_evidence.get("description", "")
        
        # Infer type from description
        rca_type = "unknown"
        if "nil pointer" in description.lower() or "null pointer" in description.lower():
            rca_type = "nil_pointer_dereference"
        elif "index out of bounds" in description.lower():
            rca_type = "index_out_of_bounds"
        elif "error_rate" in description.lower() or "error spike" in description.lower():
            rca_type = "error_rate_spike"
        elif "metric" in description.lower() or "spike" in description.lower():
            rca_type = "metric_anomaly"
        
        # Extract location
        location = self._extract_location_from_description(description)
        
        return {
            "type": rca_type,
            "description": description,
            "location": location
        }
    
    def _extract_location_from_description(self, description: str) -> str:
        """Extract file:line location from description.
        
        Args:
            description: Description text
        
        Returns:
            Location string or "unknown"
        """
        # Look for file:line pattern
        match = re.search(r'([\w/]+\.\w+):(\d+)', description)
        if match:
            return match.group(0)
        
        # Look for just filename
        match = re.search(r'([\w]+\.\w+)', description)
        if match:
            return match.group(0)
        
        return "unknown"
