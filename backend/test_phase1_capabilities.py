from types import SimpleNamespace

from app.core.capabilities import capability_for
from app.models.models import Blockchain, CaseStatus


def test_real_chain_without_provider_never_claims_observed_data():
    state = capability_for(SimpleNamespace(
        blockchain=Blockchain.ETHEREUM, is_demo=False, status=CaseStatus.REVIEW,
        analysis_summary={"processing_state": "completed", "result_state": "available"},
    ))
    assert state.data_origin.value == "none"
    assert state.provider_state.value == "not_connected"
    assert state.result_state.value == "not_available"


def test_demo_capability_distinguishes_provider_from_result():
    state = capability_for(blockchain=Blockchain.DEMO)
    assert state.data_origin.value == "demo"
    assert state.provider_state.value == "available"
    assert state.processing_state.value == "not_started"
    assert state.result_state.value == "not_available"
