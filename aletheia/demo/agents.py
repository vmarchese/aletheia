"""Mock agents for demo mode that use pre-recorded responses.

These mock agents simulate the behavior of real agents but use pre-recorded
data from demo scenarios instead of making actual API calls or LLM requests.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from aletheia.agents.base import BaseAgent
from aletheia.demo.data import DemoDataProvider
from aletheia.demo.scenario import DemoScenario, DEMO_SCENARIOS


class MockDataFetcherAgent(BaseAgent):
    """Mock data fetcher that returns pre-recorded data."""
    
    def __init__(self, config: Dict[str, Any], scratchpad, scenario: DemoScenario):
        """Initialize mock data fetcher.
        
        Args:
            config: Configuration dictionary
            scratchpad: Scratchpad instance
            scenario: Demo scenario to use
        """
        super().__init__(config, scratchpad, "data_fetcher")
        self.scenario = scenario
        self.data_provider = DemoDataProvider(scenario.id)
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute mock data collection.
        
        Returns:
            Result dictionary with status and collected data summary
        """
        # Simulate data collection delay
        import asyncio
        await asyncio.sleep(1.5)
        
        # Write pre-recorded data summary to scratchpad
        self.write_scratchpad("DATA_COLLECTED", {
            "summary": self.scenario.data_collected_summary,
            "sources": self.scenario.data_sources,
            "service": self.scenario.service_name,
            "time_window": self.scenario.time_window,
            "timestamp": datetime.now().isoformat(),
        })
        
        return {
            "status": "success",
            "message": f"Collected data from {len(self.scenario.data_sources)} sources",
            "data_summary": self.scenario.data_collected_summary,
        }


class MockPatternAnalyzerAgent(BaseAgent):
    """Mock pattern analyzer that returns pre-recorded analysis."""
    
    def __init__(self, config: Dict[str, Any], scratchpad, scenario: DemoScenario):
        """Initialize mock pattern analyzer.
        
        Args:
            config: Configuration dictionary
            scratchpad: Scratchpad instance
            scenario: Demo scenario to use
        """
        super().__init__(config, scratchpad, "pattern_analyzer")
        self.scenario = scenario
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute mock pattern analysis.
        
        Returns:
            Result dictionary with status and analysis
        """
        # Simulate analysis delay
        import asyncio
        await asyncio.sleep(2.0)
        
        # Write pre-recorded analysis to scratchpad
        self.write_scratchpad("PATTERN_ANALYSIS", self.scenario.pattern_analysis)
        
        anomaly_count = len(self.scenario.pattern_analysis.get("anomalies", []))
        cluster_count = len(self.scenario.pattern_analysis.get("error_clusters", []))
        
        return {
            "status": "success",
            "message": f"Identified {anomaly_count} anomalies and {cluster_count} error patterns",
            "analysis": self.scenario.pattern_analysis,
        }


class MockCodeInspectorAgent(BaseAgent):
    """Mock code inspector that returns pre-recorded code inspection."""
    
    def __init__(self, config: Dict[str, Any], scratchpad, scenario: DemoScenario):
        """Initialize mock code inspector.
        
        Args:
            config: Configuration dictionary
            scratchpad: Scratchpad instance
            scenario: Demo scenario to use
        """
        super().__init__(config, scratchpad, "code_inspector")
        self.scenario = scenario
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute mock code inspection.
        
        Returns:
            Result dictionary with status and inspection results
        """
        # Simulate inspection delay
        import asyncio
        await asyncio.sleep(2.5)
        
        # Write pre-recorded inspection to scratchpad
        self.write_scratchpad("CODE_INSPECTION", self.scenario.code_inspection)
        
        location_count = len(self.scenario.code_inspection.get("suspect_locations", []))
        
        return {
            "status": "success",
            "message": f"Inspected {location_count} suspect code locations",
            "inspection": self.scenario.code_inspection,
        }


class MockRootCauseAnalystAgent(BaseAgent):
    """Mock root cause analyst that returns pre-recorded diagnosis."""
    
    def __init__(self, config: Dict[str, Any], scratchpad, scenario: DemoScenario):
        """Initialize mock root cause analyst.
        
        Args:
            config: Configuration dictionary
            scratchpad: Scratchpad instance
            scenario: Demo scenario to use
        """
        super().__init__(config, scratchpad, "root_cause_analyst")
        self.scenario = scenario
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute mock root cause analysis.
        
        Returns:
            Result dictionary with status and diagnosis
        """
        # Simulate analysis delay
        import asyncio
        await asyncio.sleep(3.0)
        
        # Write pre-recorded diagnosis to scratchpad
        self.write_scratchpad("FINAL_DIAGNOSIS", self.scenario.final_diagnosis)
        
        confidence = self.scenario.final_diagnosis.get("confidence", 0.0)
        recommendation_count = len(self.scenario.final_diagnosis.get("recommendations", []))
        
        return {
            "status": "success",
            "message": f"Generated diagnosis with {confidence:.0%} confidence and {recommendation_count} recommendations",
            "diagnosis": self.scenario.final_diagnosis,
        }


def create_mock_agents(config: Dict[str, Any], scratchpad, 
                      scenario_id: str) -> Dict[str, BaseAgent]:
    """Create all mock agents for a demo scenario.
    
    Args:
        config: Configuration dictionary
        scratchpad: Scratchpad instance
        scenario_id: ID of demo scenario to use
    
    Returns:
        Dictionary mapping agent names to agent instances
    
    Raises:
        ValueError: If scenario_id is not found
    """
    if scenario_id not in DEMO_SCENARIOS:
        available = ", ".join(DEMO_SCENARIOS.keys())
        raise ValueError(f"Unknown scenario '{scenario_id}'. Available: {available}")
    
    scenario = DEMO_SCENARIOS[scenario_id]
    
    return {
        "data_fetcher": MockDataFetcherAgent(config, scratchpad, scenario),
        "pattern_analyzer": MockPatternAnalyzerAgent(config, scratchpad, scenario),
        "code_inspector": MockCodeInspectorAgent(config, scratchpad, scenario),
        "root_cause_analyst": MockRootCauseAnalystAgent(config, scratchpad, scenario),
    }
