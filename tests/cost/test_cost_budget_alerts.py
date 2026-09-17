"""Regression lock for the ``cost.py`` budget-alert import fix."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from autoinfo.cost import CostMeter


def test_cost_dashboard_budget_status_reads_list_alert_rules(tmp_path: Path) -> None:
    """``get_cost_dashboard`` reads budget alerts via ``list_alert_rules``.

    cost.py imported a never-defined ``get_budget_alerts``; the ``ImportError``
    was swallowed by the block's ``except Exception`` and ``budget_status``
    silently stayed empty.  A fake rule carrying a cost threshold proves the
    block now reaches the alerts API and populates the list — with the old
    import the call assertion and the non-empty assertion both fail.
    """
    meter = CostMeter(db_path=tmp_path / "cost.db")
    meter.log_llm_tokens(
        model="test-model",
        input_tokens=100,
        output_tokens=100,
        domain="budget-domain",
    )
    rule = SimpleNamespace(cost_threshold=1.0, cost_period="week")

    with patch("autoinfo.alerts.list_alert_rules", return_value=[rule]) as mock_rules:
        dashboard = meter.get_cost_dashboard(period="all")

    assert isinstance(dashboard["budget_status"], list)
    assert len(dashboard["budget_status"]) == 1
    assert dashboard["budget_status"][0]["domain"] == "budget-domain"
    mock_rules.assert_called_once_with(domain="budget-domain")
