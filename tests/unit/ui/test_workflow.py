"""Unit tests for investigation workflow."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from aletheia.ui.workflow import InvestigationWorkflow, create_investigation_workflow


class TestInvestigationWorkflow:
    """Tests for InvestigationWorkflow class."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    @pytest.fixture
    def workflow(self, mock_console):
        """Create InvestigationWorkflow with mock console."""
        return InvestigationWorkflow(console=mock_console)

    def test_workflow_creation(self):
        """Test InvestigationWorkflow initialization."""
        workflow = InvestigationWorkflow()
        assert workflow.console is not None
        assert workflow.menu is not None
        assert workflow.input is not None
        assert workflow.confirm is not None
        assert workflow.output is not None

    def test_workflow_with_confirmation_level(self):
        """Test workflow with specific confirmation level."""
        workflow = InvestigationWorkflow(confirmation_level="verbose")
        assert workflow.confirm.level == "verbose"

    def test_workflow_verbose_mode(self):
        """Test workflow in verbose mode."""
        workflow = InvestigationWorkflow(verbose=True)
        assert workflow.output.verbose is True

    @patch.object(InvestigationWorkflow, 'menu')
    def test_select_interaction_mode(self, mock_menu, workflow):
        """Test selecting interaction mode."""
        mock_menu.show = Mock(return_value="guided")

        result = workflow.select_interaction_mode()

        assert result == "guided"
        mock_menu.show.assert_called_once()

    @patch.object(InvestigationWorkflow, 'input')
    def test_get_problem_description(self, mock_input, workflow):
        """Test getting problem description."""
        mock_input.get_text = Mock(return_value="Test problem")

        result = workflow.get_problem_description()

        assert result == "Test problem"
        mock_input.get_text.assert_called_once()

    @patch.object(InvestigationWorkflow, 'menu')
    def test_select_time_window_preset(self, mock_menu, workflow):
        """Test selecting preset time window."""
        mock_menu.show = Mock(return_value="2h")

        result = workflow.select_time_window()

        assert result == "2h"
        mock_menu.show.assert_called_once()

    @patch.object(InvestigationWorkflow, 'menu')
    @patch.object(InvestigationWorkflow, 'input')
    def test_select_time_window_custom(self, mock_input, mock_menu, workflow):
        """Test selecting custom time window."""
        mock_menu.show = Mock(return_value="custom")
        mock_input.get_time_window = Mock(return_value="6h")

        result = workflow.select_time_window()

        assert result == "6h"
        mock_input.get_time_window.assert_called_once()

    @patch.object(InvestigationWorkflow, 'menu')
    def test_select_data_sources(self, mock_menu, workflow):
        """Test selecting data sources."""
        mock_menu.show_multiselect = Mock(return_value=["kubernetes", "prometheus"])

        result = workflow.select_data_sources()

        assert result == ["kubernetes", "prometheus"]
        mock_menu.show_multiselect.assert_called_once()

    @patch.object(InvestigationWorkflow, 'input')
    @patch.object(InvestigationWorkflow, 'confirm')
    def test_configure_kubernetes(self, mock_confirm, mock_input, workflow):
        """Test Kubernetes configuration."""
        mock_input.get_text = Mock(side_effect=["prod", "default", "app"])
        mock_input.get_service_name = Mock(return_value="app=payments")
        mock_confirm.show_and_confirm = Mock(return_value=True)

        result = workflow.configure_kubernetes()

        assert result["context"] == "prod"
        assert result["namespace"] == "default"
        assert result["pod_selector"] == "app=payments"
        assert result["container"] == "app"

    @patch.object(InvestigationWorkflow, 'input')
    def test_configure_elasticsearch(self, mock_input, workflow):
        """Test Elasticsearch configuration."""
        mock_input.get_text = Mock(side_effect=["https://es.test.com", "logs-*"])

        result = workflow.configure_elasticsearch()

        assert result["endpoint"] == "https://es.test.com"
        assert result["index"] == "logs-*"

    @patch.object(InvestigationWorkflow, 'input')
    def test_configure_prometheus(self, mock_input, workflow):
        """Test Prometheus configuration."""
        mock_input.get_text = Mock(return_value="https://prometheus.test.com")

        result = workflow.configure_prometheus()

        assert result["endpoint"] == "https://prometheus.test.com"

    @patch.object(InvestigationWorkflow, 'menu')
    def test_select_metrics(self, mock_menu, workflow):
        """Test selecting metrics."""
        mock_menu.show_multiselect = Mock(return_value=["error_rate", "p95_latency"])

        result = workflow.select_metrics()

        assert result == ["error_rate", "p95_latency"]
        mock_menu.show_multiselect.assert_called_once()

    @patch.object(InvestigationWorkflow, 'confirm')
    @patch.object(InvestigationWorkflow, 'input')
    def test_get_repository_paths(self, mock_input, mock_confirm, workflow, tmp_path):
        """Test getting repository paths."""
        # Create fake git repos
        repo1 = tmp_path / "repo1"
        repo1.mkdir()
        (repo1 / ".git").mkdir()

        mock_confirm.confirm = Mock(side_effect=[True, False, False])
        mock_input.get_repository_path = Mock(return_value=repo1)

        result = workflow.get_repository_paths(["service1", "service2"])

        assert "service1" in result
        assert result["service1"] == repo1
        assert "service2" not in result

    @patch.object(InvestigationWorkflow, 'menu')
    def test_select_action(self, mock_menu, workflow):
        """Test selecting action."""
        mock_menu.show = Mock(return_value=1)

        result = workflow.select_action(["Action 1", "Action 2", "Action 3"])

        assert result == 1
        mock_menu.show.assert_called_once()

    def test_show_diagnosis_summary(self, workflow, mock_console):
        """Test showing diagnosis summary."""
        workflow.show_diagnosis_summary(
            "Test root cause",
            confidence=0.85,
            evidence_count=5
        )

        # Should call output formatter's print_panel
        assert workflow.output.console.print.called

    @patch.object(InvestigationWorkflow, 'get_problem_description')
    @patch.object(InvestigationWorkflow, 'select_time_window')
    @patch.object(InvestigationWorkflow, 'select_data_sources')
    @patch.object(InvestigationWorkflow, 'configure_kubernetes')
    @patch.object(InvestigationWorkflow, 'select_metrics')
    def test_run_guided_workflow(
        self,
        mock_metrics,
        mock_k8s,
        mock_sources,
        mock_time,
        mock_problem,
        workflow
    ):
        """Test running complete guided workflow."""
        mock_problem.return_value = "Test problem"
        mock_time.return_value = "2h"
        mock_sources.return_value = ["kubernetes", "prometheus"]
        mock_k8s.return_value = {"context": "prod", "namespace": "default"}
        mock_metrics.return_value = ["error_rate"]

        result = workflow.run_guided_workflow()

        assert result["problem"] == "Test problem"
        assert result["time_window"] == "2h"
        assert result["data_sources"] == ["kubernetes", "prometheus"]
        assert "kubernetes" in result["configs"]
        assert result["metrics"] == ["error_rate"]


def test_create_investigation_workflow_factory():
    """Test create_investigation_workflow factory function."""
    workflow = create_investigation_workflow()
    assert isinstance(workflow, InvestigationWorkflow)
    assert workflow.confirm.level == "normal"
    assert workflow.output.verbose is False

    verbose_workflow = create_investigation_workflow(
        confirmation_level="verbose",
        verbose=True
    )
    assert verbose_workflow.confirm.level == "verbose"
    assert verbose_workflow.output.verbose is True
