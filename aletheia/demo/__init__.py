"""Demo mode for Aletheia - Pre-recorded data and responses for testing.

This module provides a demo/test mode that allows users to experience
the full guided mode workflow without requiring real data sources or LLM APIs.
"""

from aletheia.demo.data import DemoDataProvider
from aletheia.demo.scenario import DemoScenario, DEMO_SCENARIOS
from aletheia.demo.orchestrator import DemoOrchestrator, run_demo
from aletheia.demo.agents import create_mock_agents

__all__ = [
    "DemoDataProvider",
    "DemoScenario",
    "DEMO_SCENARIOS",
    "DemoOrchestrator",
    "run_demo",
    "create_mock_agents",
]
