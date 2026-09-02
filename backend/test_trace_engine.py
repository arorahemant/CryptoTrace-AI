"""Regression tests for controlled and historically-correct tracing."""
import pytest

from app.engines.trace_engine import TraceEngine
from app.providers.demo import DemoProvider


@pytest.mark.asyncio
async def test_historical_demo_window_is_anchored_to_available_history():
    result = await TraceEngine(DemoProvider()).trace(
        "0xReported001", max_hops=5, time_window_hours=2
    )
    assert result["transactions"]
    assert all(tx["timestamp"].year == 2025 for tx in result["transactions"])


@pytest.mark.asyncio
async def test_historical_demo_window_is_enforced():
    result = await TraceEngine(DemoProvider()).trace(
        "0xReported001", max_hops=5, time_window_hours=1
    )
    assert result["transactions"] == []


@pytest.mark.asyncio
async def test_trace_cycle_and_growth_limits():
    result = await TraceEngine(DemoProvider()).trace(
        "0xReported001", max_hops=2, max_transactions=2, time_window_hours=3
    )
    assert len(result["transactions"]) <= 2
    assert result["stats"]["max_hop_reached"] <= 2
