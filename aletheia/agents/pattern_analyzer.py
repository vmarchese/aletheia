"""Pattern Analyzer Agent for identifying anomalies and correlations.

This agent is responsible for:
- Identifying anomalies in logs and metrics (spikes, drops, outliers)
- Cross-correlating data from logs and metrics
- Clustering similar error messages
- Building incident timelines
- Writing results to the scratchpad's PATTERN_ANALYSIS section
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter, defaultdict
import re

from aletheia.agents.base import BaseAgent
from aletheia.llm.prompts import compose_messages, get_system_prompt, get_user_prompt_template
from aletheia.scratchpad import ScratchpadSection


class PatternAnalyzerAgent(BaseAgent):
    """Agent responsible for analyzing patterns in collected data.
    
    The Pattern Analyzer Agent:
    1. Reads the DATA_COLLECTED section from the scratchpad
    2. Identifies anomalies in metrics and logs
    3. Correlates events across different data sources
    4. Clusters similar error messages
    5. Builds a timeline of the incident
    6. Writes results to the PATTERN_ANALYSIS section
    
    Attributes:
        config: Agent configuration including analysis settings
        scratchpad: Scratchpad for reading data and writing analysis
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad: Any):
        """Initialize the Pattern Analyzer Agent.
        
        Args:
            config: Configuration dictionary with analysis settings and llm sections
            scratchpad: Scratchpad instance for agent communication
        """
        super().__init__(config, scratchpad, agent_name="pattern_analyzer")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the pattern analysis process.
        
        Args:
            **kwargs: Additional parameters for analysis
        
        Returns:
            Dictionary with execution results:
                - success: bool - Whether execution succeeded
                - anomalies_found: int - Number of anomalies detected
                - error_clusters_found: int - Number of error clusters
                - timeline_events: int - Number of timeline events
                - correlation_count: int - Number of correlations found
        
        Raises:
            ValueError: If DATA_COLLECTED section is missing or empty
        """
        # Read collected data from scratchpad
        collected_data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED)
        if not collected_data:
            raise ValueError("No data collected. Run Data Fetcher Agent first.")
        
        # Read problem description for context
        problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) or {}
        
        # Initialize analysis results
        analysis = {
            "anomalies": [],
            "correlations": [],
            "error_clusters": [],
            "timeline": []
        }
        
        # Identify anomalies in metrics
        if "prometheus" in collected_data or any("metrics" in str(v) for v in collected_data.values()):
            anomalies = self._identify_metric_anomalies(collected_data)
            analysis["anomalies"].extend(anomalies)
        
        # Identify anomalies in logs (error spikes, etc.)
        if "kubernetes" in collected_data or any("logs" in str(v) for v in collected_data.values()):
            log_anomalies = self._identify_log_anomalies(collected_data)
            analysis["anomalies"].extend(log_anomalies)
        
        # Cluster error messages
        error_clusters = self._cluster_errors(collected_data)
        analysis["error_clusters"] = error_clusters
        
        # Build timeline
        timeline = self._build_timeline(collected_data, analysis["anomalies"])
        analysis["timeline"] = timeline
        
        # Correlate data across sources
        correlations = self._correlate_data(collected_data, analysis)
        analysis["correlations"] = correlations
        
        # Write analysis to scratchpad
        self.write_scratchpad(ScratchpadSection.PATTERN_ANALYSIS, analysis)
        
        # Return execution results
        return {
            "success": True,
            "anomalies_found": len(analysis["anomalies"]),
            "error_clusters_found": len(analysis["error_clusters"]),
            "timeline_events": len(analysis["timeline"]),
            "correlation_count": len(analysis["correlations"])
        }
    
    def _identify_metric_anomalies(
        self,
        collected_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify anomalies in metric data.
        
        Args:
            collected_data: Collected data from DATA_COLLECTED section
        
        Returns:
            List of anomaly dictionaries with type, timestamp, severity, description
        """
        anomalies = []
        
        # Look for metric sources
        for source_name, source_data in collected_data.items():
            if source_data.get("error") or source_data.get("status") == "failed":
                continue
            
            # Check if this is a metric source
            summary = source_data.get("summary", "")
            if "spike" in summary.lower() or "drop" in summary.lower():
                # Parse anomalies from summary
                if "spike detected" in summary.lower():
                    # Extract spike information
                    anomaly = {
                        "type": "metric_spike",
                        "timestamp": self._extract_timestamp_from_summary(summary),
                        "severity": "critical",
                        "description": self._extract_anomaly_description(summary, "spike"),
                        "source": source_name
                    }
                    anomalies.append(anomaly)
                
                if "drop detected" in summary.lower():
                    # Extract drop information
                    anomaly = {
                        "type": "metric_drop",
                        "timestamp": self._extract_timestamp_from_summary(summary),
                        "severity": "high",
                        "description": self._extract_anomaly_description(summary, "drop"),
                        "source": source_name
                    }
                    anomalies.append(anomaly)
        
        return anomalies
    
    def _identify_log_anomalies(
        self,
        collected_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify anomalies in log data (error spikes, etc.).
        
        Args:
            collected_data: Collected data from DATA_COLLECTED section
        
        Returns:
            List of anomaly dictionaries
        """
        anomalies = []
        
        # Look for log sources
        for source_name, source_data in collected_data.items():
            if source_data.get("error") or source_data.get("status") == "failed":
                continue
            
            summary = source_data.get("summary", "")
            
            # Check for error rate spikes (heuristic: > 20% errors)
            if "ERROR" in summary or "FATAL" in summary:
                # Extract error count
                error_count = self._extract_error_count(summary)
                total_count = source_data.get("count", 0)
                
                if total_count > 0 and error_count > 0:
                    error_rate = error_count / total_count
                    
                    if error_rate > 0.2:  # More than 20% errors
                        anomaly = {
                            "type": "error_rate_spike",
                            "timestamp": self._extract_start_time(source_data),
                            "severity": "critical" if error_rate >= 0.5 else "high",
                            "description": f"High error rate: {error_count}/{total_count} ({error_rate*100:.1f}%)",
                            "source": source_name,
                            "error_rate": error_rate
                        }
                        anomalies.append(anomaly)
        
        return anomalies
    
    def _cluster_errors(
        self,
        collected_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Cluster similar error messages.
        
        Args:
            collected_data: Collected data from DATA_COLLECTED section
        
        Returns:
            List of error cluster dictionaries with pattern, count, examples
        """
        clusters = []
        
        # Collect all error messages
        error_messages = []
        
        for source_name, source_data in collected_data.items():
            if source_data.get("error") or source_data.get("status") == "failed":
                continue
            
            summary = source_data.get("summary", "")
            
            # Extract error patterns from summary
            # Look for patterns like "top error: 'X' (Nx)" or "top errors: 'X' (Nx), 'Y' (Nx)"
            # First pattern: single error
            single_pattern = r"top errors?: ['\"]([^'\"]+)['\"] \((\d+)x?\)"
            matches = re.findall(single_pattern, summary, re.IGNORECASE)
            
            for error_msg, count_str in matches:
                error_messages.append({
                    "message": error_msg,
                    "count": int(count_str),
                    "source": source_name
                })
            
            # Second pattern: multiple errors in list format 'X' (Nx), 'Y' (Ny)
            # Look for error patterns after the first match
            multi_pattern = r"['\"]([^'\"]+)['\"] \((\d+)x?\)"
            all_matches = re.findall(multi_pattern, summary, re.IGNORECASE)
            
            # Add any matches not already added
            existing_msgs = {e["message"] for e in error_messages if e["source"] == source_name}
            for error_msg, count_str in all_matches:
                if error_msg not in existing_msgs:
                    error_messages.append({
                        "message": error_msg,
                        "count": int(count_str),
                        "source": source_name
                    })
        
        # Group by normalized message
        clustered = defaultdict(list)
        for error in error_messages:
            normalized = self._normalize_error_message(error["message"])
            clustered[normalized].append(error)
        
        # Create cluster objects
        for pattern, errors in clustered.items():
            total_count = sum(e["count"] for e in errors)
            cluster = {
                "pattern": pattern,
                "count": total_count,
                "examples": [e["message"] for e in errors[:3]],  # Top 3 examples
                "sources": list(set(e["source"] for e in errors)),
                "stack_trace": self._extract_stack_trace(pattern)
            }
            clusters.append(cluster)
        
        # Sort by count (most common first)
        clusters.sort(key=lambda x: x["count"], reverse=True)
        
        return clusters
    
    def _build_timeline(
        self,
        collected_data: Dict[str, Any],
        anomalies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build a timeline of incident events.
        
        Args:
            collected_data: Collected data from DATA_COLLECTED section
            anomalies: List of detected anomalies
        
        Returns:
            List of timeline event dictionaries, sorted chronologically
        """
        timeline_events = []
        
        # Add data collection time ranges as context
        for source_name, source_data in collected_data.items():
            if source_data.get("error") or source_data.get("status") == "failed":
                continue
            
            time_range = source_data.get("time_range", "")
            if time_range and " - " in time_range:
                start_str, end_str = time_range.split(" - ")
                timeline_events.append({
                    "time": start_str,
                    "event": f"Data collection window start ({source_name})",
                    "type": "context"
                })
        
        # Add anomalies to timeline
        for anomaly in anomalies:
            timestamp = anomaly.get("timestamp")
            if timestamp:
                timeline_events.append({
                    "time": timestamp,
                    "event": f"{anomaly['type']}: {anomaly['description']}",
                    "type": "anomaly",
                    "severity": anomaly.get("severity", "unknown")
                })
        
        # Sort by timestamp
        timeline_events.sort(key=lambda x: x["time"])
        
        return timeline_events
    
    def _correlate_data(
        self,
        collected_data: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Correlate events across different data sources.
        
        Args:
            collected_data: Collected data from DATA_COLLECTED section
            analysis: Current analysis with anomalies and clusters
        
        Returns:
            List of correlation dictionaries
        """
        correlations = []
        
        # Correlate metric anomalies with error clusters
        metric_anomalies = [a for a in analysis["anomalies"] if "metric" in a.get("type", "")]
        log_anomalies = [a for a in analysis["anomalies"] if "error" in a.get("type", "")]
        
        # Temporal alignment: Check if metric spike coincides with error spike
        if metric_anomalies and log_anomalies:
            for metric_anom in metric_anomalies:
                for log_anom in log_anomalies:
                    # Check if timestamps are close (within 5 minutes)
                    if self._timestamps_close(
                        metric_anom.get("timestamp"),
                        log_anom.get("timestamp"),
                        threshold_minutes=5
                    ):
                        correlation = {
                            "type": "temporal_alignment",
                            "description": f"Metric {metric_anom['type']} coincides with {log_anom['type']}",
                            "confidence": 0.85,
                            "events": [metric_anom, log_anom]
                        }
                        correlations.append(correlation)
        
        # Check for deployment correlations (if mentioned in problem description)
        problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) or {}
        description = problem.get("description", "")
        
        if "deploy" in description.lower() or "rollout" in description.lower():
            # Check if first anomaly happened shortly after mentioned deployment
            if analysis["anomalies"]:
                first_anomaly = min(analysis["anomalies"], key=lambda x: x.get("timestamp", ""))
                correlation = {
                    "type": "deployment_correlation",
                    "description": "Anomalies started after deployment mentioned in problem description",
                    "confidence": 0.75,
                    "events": [first_anomaly]
                }
                correlations.append(correlation)
        
        return correlations
    
    # Helper methods
    
    def _normalize_error_message(self, message: str) -> str:
        """Normalize error message by removing variable parts.
        
        Args:
            message: Original error message
        
        Returns:
            Normalized error message pattern
        """
        # Remove UUIDs first (before number replacement)
        normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', message, flags=re.IGNORECASE)
        # Remove hex values (before number replacement) - use placeholder without digits
        normalized = re.sub(r'0x[0-9a-fA-F]+', 'HEX', normalized)
        # Remove file paths
        normalized = re.sub(r'/[\w/.-]+', '/PATH', normalized)
        # Remove numbers last
        normalized = re.sub(r'\d+', 'N', normalized)
        
        return normalized.strip()
    
    def _extract_stack_trace(self, error_pattern: str) -> Optional[str]:
        """Extract stack trace from error pattern if present.
        
        Args:
            error_pattern: Error message pattern
        
        Returns:
            Stack trace string or None
        """
        # Look for file:line patterns
        stack_pattern = r'(\w+\.\w+:\d+)'
        matches = re.findall(stack_pattern, error_pattern)
        
        if matches:
            return " → ".join(matches)
        
        return None
    
    def _extract_timestamp_from_summary(self, summary: str) -> str:
        """Extract timestamp from summary text.
        
        Args:
            summary: Summary text
        
        Returns:
            ISO format timestamp string, or current time if not found
        """
        # Try to extract ISO timestamp
        iso_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        match = re.search(iso_pattern, summary)
        
        if match:
            return match.group(0)
        
        # Return current time as fallback
        return datetime.now().isoformat()
    
    def _extract_anomaly_description(self, summary: str, anomaly_type: str) -> str:
        """Extract anomaly description from summary.
        
        Args:
            summary: Summary text
            anomaly_type: Type of anomaly (spike, drop)
        
        Returns:
            Description string
        """
        # Extract the part of summary related to the anomaly
        if anomaly_type.lower() in summary.lower():
            # Find the sentence containing the anomaly type
            sentences = summary.split(';')
            for sentence in sentences:
                if anomaly_type.lower() in sentence.lower():
                    return sentence.strip()
        
        return f"{anomaly_type.capitalize()} detected in metrics"
    
    def _extract_error_count(self, summary: str) -> int:
        """Extract error count from summary.
        
        Args:
            summary: Summary text
        
        Returns:
            Error count integer
        """
        # Look for patterns like "X ERROR" or "X FATAL"
        # Use findall to get all matches and sum them
        pattern = r'(\d+)\s+(?:ERROR|FATAL)'
        matches = re.findall(pattern, summary, re.IGNORECASE)
        
        if matches:
            return sum(int(m) for m in matches)
        
        return 0
    
    def _extract_start_time(self, source_data: Dict[str, Any]) -> str:
        """Extract start time from source data.
        
        Args:
            source_data: Source data dictionary
        
        Returns:
            ISO format timestamp string
        """
        time_range = source_data.get("time_range", "")
        
        if time_range and " - " in time_range:
            start_str = time_range.split(" - ")[0]
            return start_str
        
        return datetime.now().isoformat()
    
    def _timestamps_close(
        self,
        timestamp1: Optional[str],
        timestamp2: Optional[str],
        threshold_minutes: int = 5
    ) -> bool:
        """Check if two timestamps are close to each other.
        
        Args:
            timestamp1: First timestamp (ISO format)
            timestamp2: Second timestamp (ISO format)
            threshold_minutes: Maximum minutes apart to be considered close
        
        Returns:
            True if timestamps are within threshold, False otherwise
        """
        if not timestamp1 or not timestamp2:
            return False
        
        try:
            # Parse timestamps
            dt1 = datetime.fromisoformat(timestamp1.replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(timestamp2.replace('Z', '+00:00'))
            
            # Calculate difference
            diff = abs((dt1 - dt2).total_seconds())
            
            return diff <= (threshold_minutes * 60)
        except (ValueError, AttributeError):
            return False
