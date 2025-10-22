"""Unit tests for Prometheus Semantic Kernel plugin."""

import asyncio
import json
import pytest
import aiohttp
from unittest.mock import Mock, patch, AsyncMock
from aletheia.plugins.prometheus_plugin import PrometheusPlugin, PROMQL_TEMPLATES


class TestPrometheusPluginInitialization:
    """Tests for PrometheusPlugin initialization."""
    
    def test_init_with_valid_config(self):
        """Test plugin initialization with valid configuration."""
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        assert plugin.endpoint == "http://prometheus:9090"
        assert plugin.timeout == 30
    
    def test_init_without_endpoint_raises_error(self):
        """Test that initialization without endpoint raises ValueError."""
        config = {}
        
        with pytest.raises(ValueError, match="'endpoint' is required"):
            PrometheusPlugin(config)


class TestFetchPrometheusMetrics:
    """Tests for fetch_prometheus_metrics function."""
    
    @pytest.mark.asyncio
    async def test_fetch_metrics_basic(self):
        """Test basic metric fetching."""
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        mock_response_data = {
            "status": "success",
            "data": {"result": [{"metric": {"__name__": "up"}, "value": [1698854400, "1"]}]}
        }
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status.return_value = None
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch.object(plugin, '_get_session', return_value=mock_session):
            result_json = await plugin.fetch_prometheus_metrics(query="up")
        
        result = json.loads(result_json)
        assert "query" in result
        assert result["query"] == "up"


class TestListPromQLTemplates:
    """Tests for list_promql_templates function."""
    
    @pytest.mark.asyncio
    async def test_list_templates(self):
        """Test listing templates."""
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        result_json = await plugin.list_promql_templates()
        result = json.loads(result_json)
        
        assert "templates" in result
        assert "count" in result


class TestAsyncBehavior:
    """Tests for async behavior."""
    
    @pytest.mark.asyncio
    async def test_all_functions_are_async(self):
        """Test that all functions are async."""
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        assert asyncio.iscoroutinefunction(plugin.fetch_prometheus_metrics)
        assert asyncio.iscoroutinefunction(plugin.list_promql_templates)

