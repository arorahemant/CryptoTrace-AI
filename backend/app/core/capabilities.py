"""Shared capability contract; absence of demo data never proves observation."""
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class DataOrigin(str, Enum):
    NONE = "none"
    DEMO = "demo"
    OBSERVED = "observed"


class ProviderState(str, Enum):
    AVAILABLE = "available"
    NOT_CONNECTED = "not_connected"


class ProcessingState(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResultState(str, Enum):
    NOT_AVAILABLE = "not_available"
    AVAILABLE = "available"
    EMPTY = "empty"
    PARTIAL = "partial"
    STALE = "stale"


class CapabilityState(BaseModel):
    run_id: str | None = None
    model_version: int | None = None
    data_origin: DataOrigin = DataOrigin.NONE
    provider_state: ProviderState = ProviderState.NOT_CONNECTED
    processing_state: ProcessingState = ProcessingState.NOT_STARTED
    result_state: ResultState = ResultState.NOT_AVAILABLE
    provider: str | None = None
    processed_at: datetime | None = None
    data_as_of: datetime | None = None
    limitations: list[str] = Field(default_factory=list)


def capability_for(case=None, *, blockchain=None) -> CapabilityState:
    chain = blockchain if blockchain is not None else getattr(case, "blockchain", None)
    chain = getattr(chain, "value", chain)
    if chain != "demo":
        # No real provider is implemented. Do not trust legacy is_demo flags,
        # arbitrary stored summaries, or the existence of a real-chain case.
        return CapabilityState(limitations=["provider_not_connected", "no_blockchain_observations"])
    summary = getattr(case, "analysis_summary", None) or {}
    capability = CapabilityState(
        data_origin=DataOrigin.DEMO,
        provider_state=ProviderState.AVAILABLE,
        provider="demo",
        limitations=["synthetic_data", "no_live_blockchain_provider", "no_external_action_verified"],
    )
    legacy_snapshot = getattr(getattr(case, "status", None), "value", None) in {"completed", "review", "investigating"}
    if case is not None and (summary or legacy_snapshot):
        capability.run_id = summary.get("run_id") or (f"legacy:{case.id}" if getattr(case, "id", None) else None)
        capability.model_version = summary.get("model_version")
    if summary:
        capability.processing_state = ProcessingState(summary.get("processing_state", "not_started"))
        capability.result_state = ResultState(summary.get("result_state", "not_available"))
        capability.processed_at = datetime.fromisoformat(summary["processed_at"]) if summary.get("processed_at") else None
        capability.data_as_of = datetime.fromisoformat(summary["data_as_of"]) if summary.get("data_as_of") else None
        capability.limitations += summary.get("limitations", [])
    elif getattr(getattr(case, "status", None), "value", None) in {"completed", "review", "investigating"}:
        capability.result_state = ResultState.STALE
        capability.limitations.append("legacy_analysis_metadata_unavailable")
    return capability


def capability_payload(case) -> dict:
    return capability_for(case).model_dump(mode="json")


def analysis_summary(stats: dict, transactions: list[dict]) -> dict:
    failed = not transactions and stats.get("provider_errors", 0) > 0
    result = "partial" if stats.get("trace_status") == "partial" else "available" if transactions else "empty"
    return {
        "processing_state": "failed" if failed else "completed",
        "result_state": "not_available" if failed else result,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "data_as_of": max((tx["timestamp"] for tx in transactions), default=None).isoformat() if transactions else None,
        "limitations": ["bounded_trace"] + (["incomplete_trace"] if result == "partial" else []),
        "stats": stats,
    }
