"""Demo orchestrator for running investigations with mock agents.

This orchestrator runs the guided mode workflow using mock agents and
pre-recorded data from demo scenarios.
"""

import asyncio
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from aletheia.demo.scenario import DEMO_SCENARIOS, DemoScenario
from aletheia.demo.agents import create_mock_agents
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.ui.output import OutputFormatter


class DemoOrchestrator:
    """Orchestrates demo investigations with mock agents."""
    
    def __init__(self, config: Dict[str, Any], scratchpad: Scratchpad, 
                 scenario_id: str, console: Optional[Console] = None):
        """Initialize demo orchestrator.
        
        Args:
            config: Configuration dictionary
            scratchpad: Scratchpad instance
            scenario_id: ID of demo scenario to run
            console: Rich console for output (creates new if None)
        
        Raises:
            ValueError: If scenario_id is not found
        """
        if scenario_id not in DEMO_SCENARIOS:
            available = ", ".join(DEMO_SCENARIOS.keys())
            raise ValueError(f"Unknown scenario '{scenario_id}'. Available: {available}")
        
        self.config = config
        self.scratchpad = scratchpad
        self.scenario = DEMO_SCENARIOS[scenario_id]
        self.console = console or Console()
        self.formatter = OutputFormatter(self.console, verbose=False)
        
        # Create mock agents
        self.agents = create_mock_agents(config, scratchpad, scenario_id)
    
    def display_scenario_info(self) -> None:
        """Display information about the demo scenario."""
        self.console.print("\n")
        self.console.print(Panel.fit(
            f"[bold cyan]{self.scenario.name}[/bold cyan]\n\n"
            f"{self.scenario.description}\n\n"
            f"[dim]This is a demo scenario with pre-recorded data.[/dim]",
            title="Demo Scenario",
            border_style="cyan",
        ))
        self.console.print("")
    
    def display_problem_description(self) -> None:
        """Display the problem description."""
        self.formatter.print_header("Problem Description", level=2)
        self.console.print(self.scenario.problem_description.strip())
        self.console.print("")
    
    async def run_investigation(self) -> Dict[str, Any]:
        """Run the complete demo investigation workflow.
        
        Returns:
            Result dictionary with investigation status
        """
        try:
            # Display scenario info
            self.display_scenario_info()
            
            # Display problem description
            self.display_problem_description()
            
            # Confirm to proceed
            if not Confirm.ask("Start investigation?", default=True):
                return {"status": "cancelled"}
            
            # Phase 1: Data Collection
            self.console.print("")
            self.formatter.print_header("Phase 1: Data Collection", level=2)
            self.formatter.print_status(f"Collecting data from {len(self.scenario.data_sources)} sources...", "info")
            
            result = await self.agents["data_fetcher"].execute()
            if result["status"] == "success":
                self.formatter.print_status(result["message"], "success")
            else:
                self.formatter.print_error("Data collection failed")
                return {"status": "failed", "phase": "data_collection"}
            
            # Show data summary
            self.console.print("\n[bold]Data Collection Summary:[/bold]")
            self.console.print(result["data_summary"])
            
            # Confirm to proceed
            self.console.print("")
            if not Confirm.ask("Proceed to pattern analysis?", default=True):
                return {"status": "cancelled", "phase": "data_collection"}
            
            # Phase 2: Pattern Analysis
            self.console.print("")
            self.formatter.print_header("Phase 2: Pattern Analysis", level=2)
            self.formatter.print_status("Analyzing patterns in collected data...", "info")
            
            result = await self.agents["pattern_analyzer"].execute()
            if result["status"] == "success":
                self.formatter.print_status(result["message"], "success")
            else:
                self.formatter.print_error("Pattern analysis failed")
                return {"status": "failed", "phase": "pattern_analysis"}
            
            # Show analysis summary
            analysis = result["analysis"]
            self.console.print(f"\n[bold]Pattern Analysis Summary:[/bold]")
            self.console.print(f"• {len(analysis.get('anomalies', []))} anomalies detected")
            self.console.print(f"• {len(analysis.get('error_clusters', []))} error patterns identified")
            self.console.print(f"• {len(analysis.get('correlations', []))} correlations found")
            
            # Show timeline
            if "timeline" in analysis:
                self.console.print("\n[bold]Incident Timeline:[/bold]")
                for event in analysis["timeline"]:
                    self.console.print(f"  {event['time']}: {event['event']}")
            
            # Confirm to proceed
            self.console.print("")
            if not Confirm.ask("Proceed to code inspection?", default=True):
                return {"status": "cancelled", "phase": "pattern_analysis"}
            
            # Phase 3: Code Inspection
            self.console.print("")
            self.formatter.print_header("Phase 3: Code Inspection", level=2)
            self.formatter.print_status(f"Inspecting code in {len(self.scenario.repositories)} repositories...", "info")
            
            result = await self.agents["code_inspector"].execute()
            if result["status"] == "success":
                self.formatter.print_status(result["message"], "success")
            else:
                self.formatter.print_error("Code inspection failed")
                return {"status": "failed", "phase": "code_inspection"}
            
            # Show inspection summary
            inspection = result["inspection"]
            self.console.print(f"\n[bold]Code Inspection Summary:[/bold]")
            for location in inspection.get("suspect_locations", []):
                self.console.print(
                    f"• {location['file']}:{location['line']} in {location['function']}()"
                )
                self.console.print(f"  [{location['severity']}] {location['issue']}")
            
            # Confirm to proceed
            self.console.print("")
            if not Confirm.ask("Proceed to root cause analysis?", default=True):
                return {"status": "cancelled", "phase": "code_inspection"}
            
            # Phase 4: Root Cause Analysis
            self.console.print("")
            self.formatter.print_header("Phase 4: Root Cause Analysis", level=2)
            self.formatter.print_status("Synthesizing findings and generating diagnosis...", "info")
            
            result = await self.agents["root_cause_analyst"].execute()
            if result["status"] == "success":
                self.formatter.print_status(result["message"], "success")
            else:
                self.formatter.print_error("Root cause analysis failed")
                return {"status": "failed", "phase": "root_cause_analysis"}
            
            # Display final diagnosis
            self.console.print("")
            diagnosis_data = result["diagnosis"]
            self.formatter.print_diagnosis(
                root_cause=diagnosis_data.get("root_cause", "Unknown"),
                description=diagnosis_data.get("hypothesis", ""),
                evidence=diagnosis_data.get("evidence", []),
                actions=diagnosis_data.get("recommendations", []),
                confidence=diagnosis_data.get("confidence", 0.0),
                show_action_menu=False,
            )
            
            return {
                "status": "completed",
                "diagnosis": diagnosis_data,
            }
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Investigation interrupted[/yellow]")
            return {"status": "interrupted"}
        except Exception as e:
            self.formatter.print_error(f"Investigation failed: {e}")
            return {"status": "failed", "error": str(e)}


async def run_demo(scenario_id: str, config: Dict[str, Any], 
                  scratchpad: Scratchpad) -> Dict[str, Any]:
    """Run a demo investigation scenario.
    
    Args:
        scenario_id: ID of demo scenario to run
        config: Configuration dictionary
        scratchpad: Scratchpad instance
    
    Returns:
        Result dictionary with investigation status
    
    Raises:
        ValueError: If scenario_id is not found
    """
    orchestrator = DemoOrchestrator(config, scratchpad, scenario_id)
    return await orchestrator.run_investigation()
