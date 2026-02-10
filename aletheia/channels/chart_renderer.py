"""Render Chart model objects as PNG images using matplotlib."""

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import structlog  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from aletheia.agents.model import Chart, ChartData  # noqa: E402

logger = structlog.get_logger(__name__)

# Color palette matching the web frontend ECharts theme.
SERIES_COLORS = [
    "#58a6ff",
    "#3fb950",
    "#d2a8ff",
    "#f0883e",
    "#ff7b72",
    "#79c0ff",
    "#56d364",
]

# Dark theme colours (GitHub-dark inspired).
_BG = "#0d1117"
_FG = "#c9d1d9"
_BORDER = "#30363d"
_LEGEND_BG = "#161b22"


def render_chart_to_png(chart_data: dict[str, Any]) -> io.BytesIO | None:
    """Render a chart dict to a PNG image in memory.

    Args:
        chart_data: A dict matching the ``Chart`` schema (name, display_hint, data).

    Returns:
        A :class:`io.BytesIO` containing PNG bytes (seeked to 0), or ``None``
        if rendering fails or the chart has no data.
    """
    try:
        chart = Chart(**chart_data)

        if not chart.data:
            logger.warning("Chart has no data", chart_name=chart.name)
            return None

        data = chart.data[0]
        hint = chart.display_hint

        if hint == "pie":
            fig = _render_pie(chart.name, data)
        else:
            fig = _render_line_area(
                chart.name,
                data,
                is_area=hint in ("basic_area", "stacked_areas"),
                is_stacked=hint in ("stacked_lines", "stacked_areas"),
            )

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception:
        logger.exception("Failed to render chart", chart_name=chart_data.get("name"))
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_style(fig: Figure, ax: Any) -> None:
    """Apply dark-theme styling to a figure and axes."""
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.tick_params(colors=_FG)
    ax.xaxis.label.set_color(_FG)
    ax.yaxis.label.set_color(_FG)
    ax.title.set_color(_FG)
    for spine in ax.spines.values():
        spine.set_color(_BORDER)
    ax.grid(True, color=_BORDER, alpha=0.3)


def _render_pie(name: str, chart_data: ChartData) -> Figure:
    """Render a donut-style pie chart."""
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor(_BG)

    metric = chart_data.metrics[0]
    colors = SERIES_COLORS[: len(chart_data.labels)]

    result: Any = ax.pie(
        metric.values,
        labels=chart_data.labels,
        autopct="%1.1f%%",
        pctdistance=0.85,
        colors=colors,
        wedgeprops={"width": 0.3, "edgecolor": _BG},
        textprops={"color": _FG},
    )
    autotexts = result[2]
    for autotext in autotexts:
        autotext.set_color(_FG)

    ax.set_title(name, color=_FG, fontsize=14, fontweight="bold", pad=20)
    ax.legend(
        chart_data.labels,
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        facecolor=_LEGEND_BG,
        edgecolor=_BORDER,
        labelcolor=_FG,
    )
    return fig


def _render_line_area(
    name: str,
    chart_data: ChartData,
    *,
    is_area: bool,
    is_stacked: bool,
) -> Figure:
    """Render a line or area chart (handles all non-pie hints)."""
    fig, ax = plt.subplots(figsize=(10, 6))
    _apply_style(fig, ax)

    labels = chart_data.labels
    x = list(range(len(labels)))

    if is_stacked and is_area:
        # stacked_areas → stackplot
        values_list = [m.values for m in chart_data.metrics]
        legend_labels = [f"{m.name} ({m.unit})" for m in chart_data.metrics]
        ax.stackplot(
            x,
            *values_list,
            labels=legend_labels,
            colors=SERIES_COLORS[: len(chart_data.metrics)],
            alpha=0.7,
        )
    else:
        cumulative = [0.0] * len(labels)
        for i, metric in enumerate(chart_data.metrics):
            color = SERIES_COLORS[i % len(SERIES_COLORS)]
            label = f"{metric.name} ({metric.unit})"

            if is_stacked:
                y = [cumulative[j] + metric.values[j] for j in range(len(labels))]
                ax.plot(x, y, label=label, color=color, linewidth=2)
                cumulative = y
            else:
                ax.plot(x, metric.values, label=label, color=color, linewidth=2)

            if is_area and not is_stacked:
                ax.fill_between(x, metric.values, alpha=0.3, color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_title(name, fontsize=14, fontweight="bold", pad=15)
    ax.legend(
        facecolor=_LEGEND_BG,
        edgecolor=_BORDER,
        labelcolor=_FG,
    )
    fig.tight_layout()
    return fig
