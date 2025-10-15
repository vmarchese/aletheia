"""Semantic Kernel plugins for external data source operations.

This package contains SK plugins that expose operations for Kubernetes,
Prometheus, Git, and other external systems as kernel functions that can
be automatically invoked by SK agents.
"""

from aletheia.plugins.kubernetes_plugin import KubernetesPlugin

__all__ = ["KubernetesPlugin"]
