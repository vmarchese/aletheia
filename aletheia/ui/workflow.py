"""
Investigation workflow for guided mode.

Orchestrates the user interaction flow for incident investigation.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List
from pathlib import Path
from rich.console import Console

from aletheia.ui.menu import Menu, MenuItem
from aletheia.ui.input import InputHandler
from aletheia.ui.confirmation import ConfirmationManager, ConfirmationLevel
from aletheia.ui.output import OutputFormatter


class InvestigationWorkflow:
    """Manages the guided mode investigation workflow."""

    def __init__(
        self,
        confirmation_level: ConfirmationLevel = "normal",
        verbose: bool = False,
        console: Optional[Console] = None
    ):
        """
        Initialize investigation workflow.

        Args:
            confirmation_level: Confirmation level for prompts
            verbose: Enable verbose output
            console: Rich console instance
        """
        self.console = console or Console()
        self.menu = Menu(self.console)
        self.input = InputHandler(self.console)
        self.confirm = ConfirmationManager(confirmation_level, self.console)
        self.output = OutputFormatter(self.console, verbose)

    def select_interaction_mode(self) -> str:
        """
        Prompt user to select interaction mode.

        Returns:
            Selected mode ('guided' or 'conversational')
        """
        items = [
            MenuItem(
                label="Guided",
                value="guided",
                description="Menu-driven workflow (recommended)"
            ),
            MenuItem(
                label="Conversational",
                value="conversational",
                description="Natural language interaction"
            )
        ]

        return self.menu.show(
            "Select interaction mode:",
            items,
            default=1
        )

    def get_problem_description(self) -> str:
        """
        Prompt user for problem description.

        Returns:
            Problem description text
        """
        self.output.print_header("PROBLEM DESCRIPTION", level=2)

        description = self.input.get_text(
            "Describe the problem you're investigating"
        )

        return description

    def select_time_window(self) -> str:
        """
        Prompt user to select time window for investigation.

        Returns:
            Time window string (e.g., "2h", "30m", "1d")
        """
        items = [
            MenuItem(label="Last 30 minutes", value="30m"),
            MenuItem(label="Last 2 hours", value="2h"),
            MenuItem(label="Last 4 hours", value="4h"),
            MenuItem(label="Last 24 hours", value="1d"),
            MenuItem(label="Custom...", value="custom")
        ]

        selection = self.menu.show(
            "Choose a time window:",
            items,
            default=2  # Default to "Last 2 hours"
        )

        if selection == "custom":
            return self.input.get_time_window()

        return selection

    def select_data_sources(self) -> List[str]:
        """
        Prompt user to select data sources.

        Returns:
            List of selected data source names
        """
        items = [
            MenuItem(
                label="Kubernetes",
                value="kubernetes",
                description="Pod logs via kubectl"
            ),
            MenuItem(
                label="Elasticsearch",
                value="elasticsearch",
                description="Centralized logs"
            ),
            MenuItem(
                label="Prometheus",
                value="prometheus",
                description="Metrics and alerts"
            )
        ]

        sources = self.menu.show_multiselect(
            "Select data sources to fetch:",
            items,
            defaults=[1]  # Default to Kubernetes
        )

        return sources

    def configure_kubernetes(self) -> Dict[str, str]:
        """
        Prompt user for Kubernetes configuration.

        Returns:
            Dictionary with Kubernetes config (context, namespace, pod_selector)
        """
        self.output.print_header("KUBERNETES CONFIGURATION", level=3)

        config = {}

        # Context
        context = self.input.get_text(
            "Kubernetes context",
            default="prod"
        )
        config["context"] = context

        # Namespace
        namespace = self.input.get_text(
            "Namespace",
            default="default"
        )
        config["namespace"] = namespace

        # Pod selector
        pod_selector = self.input.get_service_name(
            "Pod selector (e.g., app=payments-svc)"
        )
        config["pod_selector"] = pod_selector

        # Container (optional)
        container = self.input.get_text(
            "Container name (leave blank for default)",
            default="app"
        )
        if container:
            config["container"] = container

        # Show summary and confirm
        summary = f"Context: {context}, Namespace: {namespace}, Pods: {pod_selector}"
        if not self.confirm.show_and_confirm(summary, category="data_fetch"):
            # User cancelled, recurse to re-configure
            return self.configure_kubernetes()

        return config

    def configure_elasticsearch(self) -> Dict[str, Any]:
        """
        Prompt user for Elasticsearch configuration.

        Returns:
            Dictionary with Elasticsearch config
        """
        self.output.print_header("ELASTICSEARCH CONFIGURATION", level=3)

        config = {}

        # Endpoint
        endpoint = self.input.get_text(
            "Elasticsearch endpoint",
            default="https://es.company.com"
        )
        config["endpoint"] = endpoint

        # Index pattern
        index = self.input.get_text(
            "Index pattern",
            default="logs-*"
        )
        config["index"] = index

        return config

    def configure_prometheus(self) -> Dict[str, str]:
        """
        Prompt user for Prometheus configuration.

        Returns:
            Dictionary with Prometheus config
        """
        self.output.print_header("PROMETHEUS CONFIGURATION", level=3)

        config = {}

        # Endpoint
        endpoint = self.input.get_text(
            "Prometheus endpoint",
            default="https://prometheus.company.com"
        )
        config["endpoint"] = endpoint

        return config

    def select_metrics(self) -> List[str]:
        """
        Prompt user to select which metrics to fetch.

        Returns:
            List of selected metric types
        """
        items = [
            MenuItem(
                label="Error rate (5xx)",
                value="error_rate",
                description="HTTP 500+ error rate"
            ),
            MenuItem(
                label="P95 latency",
                value="p95_latency",
                description="95th percentile response time"
            ),
            MenuItem(
                label="CPU/Memory saturation",
                value="resource_saturation",
                description="Resource usage metrics"
            ),
            MenuItem(
                label="Custom query",
                value="custom",
                description="Enter custom PromQL query"
            )
        ]

        metrics = self.menu.show_multiselect(
            "Select metrics to fetch:",
            items,
            defaults=[1, 2]  # Default to error rate and P95 latency
        )

        return metrics

    def get_repository_paths(self, service_names: List[str]) -> Dict[str, Path]:
        """
        Prompt user for repository paths for code analysis.

        Args:
            service_names: List of detected service names

        Returns:
            Dictionary mapping service names to repository paths
        """
        self.output.print_header("CODE REPOSITORY ACCESS", level=2)

        if service_names:
            self.output.print_status(
                f"Detected services: {', '.join(service_names)}",
                status="info"
            )

        repo_paths = {}

        for service in service_names:
            # Ask if user wants to provide repo for this service
            if not self.confirm.confirm(
                f"Provide repository for '{service}'?",
                category="repository_access",
                default=True
            ):
                continue

            # Get repository path
            repo_path = self.input.get_repository_path(
                f"Repository path for '{service}'"
            )
            repo_paths[service] = repo_path

        # Allow adding additional repositories
        while True:
            if not self.confirm.confirm(
                "Add another repository?",
                category="repository_access",
                default=False
            ):
                break

            service_name = self.input.get_service_name("Service name")
            repo_path = self.input.get_repository_path(
                f"Repository path for '{service_name}'"
            )
            repo_paths[service_name] = repo_path

        return repo_paths

    def select_action(self, actions: List[str]) -> int:
        """
        Show action menu and get user selection.

        Args:
            actions: List of action descriptions

        Returns:
            Selected action index (0-based)
        """
        self.output.print_header("CHOOSE AN ACTION", level=3)

        items = [MenuItem(label=action, value=idx) for idx, action in enumerate(actions)]

        return self.menu.show("", items)

    def show_diagnosis_summary(
        self,
        root_cause: str,
        confidence: float,
        evidence_count: int
    ) -> None:
        """
        Show a brief diagnosis summary.

        Args:
            root_cause: Root cause summary
            confidence: Confidence score
            evidence_count: Number of evidence items
        """
        confidence_pct = int(confidence * 100)

        self.output.print_panel(
            f"[bold]Root Cause:[/bold] {root_cause}\n"
            f"[bold]Confidence:[/bold] {confidence_pct}%\n"
            f"[bold]Evidence Items:[/bold] {evidence_count}",
            title="Diagnosis Summary",
            border_style="green"
        )

    def run_guided_workflow(self) -> Dict[str, Any]:
        """
        Run the complete guided investigation workflow.

        Returns:
            Dictionary with all collected workflow data
        """
        workflow_data = {}

        # Problem description
        problem = self.get_problem_description()
        workflow_data["problem"] = problem

        # Time window
        time_window = self.select_time_window()
        workflow_data["time_window"] = time_window

        # Data sources
        data_sources = self.select_data_sources()
        workflow_data["data_sources"] = data_sources

        # Configure each selected data source
        configs = {}
        for source in data_sources:
            if source == "kubernetes":
                configs["kubernetes"] = self.configure_kubernetes()
            elif source == "elasticsearch":
                configs["elasticsearch"] = self.configure_elasticsearch()
            elif source == "prometheus":
                configs["prometheus"] = self.configure_prometheus()

        workflow_data["configs"] = configs

        # If Prometheus selected, ask which metrics
        if "prometheus" in data_sources:
            metrics = self.select_metrics()
            workflow_data["metrics"] = metrics

        return workflow_data


def create_investigation_workflow(
    confirmation_level: ConfirmationLevel = "normal",
    verbose: bool = False,
    console: Optional[Console] = None
) -> InvestigationWorkflow:
    """
    Factory function to create an InvestigationWorkflow instance.

    Args:
        confirmation_level: Confirmation level
        verbose: Enable verbose output
        console: Optional Rich console instance

    Returns:
        InvestigationWorkflow instance
    """
    return InvestigationWorkflow(confirmation_level, verbose, console)
