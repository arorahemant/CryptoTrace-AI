"""Public case reference and comparison safety coverage."""
from fastapi.testclient import TestClient

from app.main import app
from app.core.wallet_validation import validate_wallet_format
from app.models.models import Blockchain
from app.services.public_case_service import (
    ANALYZABLE_PUBLIC_CASE_ID,
    ANALYZABLE_SOURCE_URL,
    ANALYZABLE_WALLET,
    PUBLIC_CASE_ID,
    SOURCE_URL,
    build_comparison,
    classify_comparison,
    get_public_case,
    list_public_cases,
)


def test_public_case_is_source_backed_and_does_not_invent_wallet_data():
    cases = list_public_cases()
    assert len(cases) == 2
    case = next(item for item in cases if item["case_id"] == PUBLIC_CASE_ID)
    assert case["case_id"] == PUBLIC_CASE_ID
    assert case["case_label"] == "PUBLIC CASE REFERENCE"
    assert case["provenance"] == "PUBLIC_CASE_REFERENCE"
    assert case["source_url"] == SOURCE_URL
    assert case["source_authority"] == "Hyderabad City Police"
    assert case["publicly_disclosed_wallets"] == []
    assert case["wallet_disclosure_note"] == "NOT PUBLICLY DISCLOSED"
    assert case["disclosed_transaction_references"] == []
    assert case["transaction_disclosure_note"] == "NOT PUBLICLY DISCLOSED"


def test_second_public_case_preserves_authoritative_wallet_chain_and_missing_hash():
    case = get_public_case(ANALYZABLE_PUBLIC_CASE_ID)
    assert case is not None
    assert case["source_url"] == ANALYZABLE_SOURCE_URL
    assert case["source_authority"].startswith("U.S. Department of Justice")
    assert case["blockchain"] == "BITCOIN"
    assert case["asset"] == "BTC"
    assert case["publicly_disclosed_wallets"] == [ANALYZABLE_WALLET]
    assert validate_wallet_format(ANALYZABLE_WALLET, Blockchain.BITCOIN)
    assert case["disclosed_transaction_references"] == []
    assert case["transaction_disclosure_note"].startswith("NOT PUBLICLY DISCLOSED")
    assert case["analysis_availability"] == "NOT OBSERVABLE WITH CURRENT PROVIDER"
    assert any("20.2891382 BTC" in fact["value"] for fact in case["facts"])


def test_second_public_case_does_not_fake_analysis_or_matches():
    comparison = build_comparison(ANALYZABLE_PUBLIC_CASE_ID)
    assert comparison is not None
    assert comparison["case"]["publicly_disclosed_wallets"] == [ANALYZABLE_WALLET]
    assert comparison["cryptotrace"]["status"] == "NOT_OBSERVABLE"
    assert comparison["cryptotrace"]["wallets"] == []
    assert comparison["cryptotrace"]["transaction_references"] == []
    assert comparison["alignment"]["matched"] == 0
    assert comparison["alignment"]["partial"] == 0
    assert comparison["alignment"]["not_comparable"] == 1
    assert all(row["result"] in {"NOT_OBSERVABLE", "NOT_COMPARABLE"} for row in comparison["rows"])
    assert any(ANALYZABLE_WALLET in evidence for row in comparison["rows"] for evidence in row["evidence"])
    assert "No synthetic investigation was run" in comparison["cryptotrace"]["message"]


def test_comparison_is_reference_only_when_public_chain_identifiers_are_missing():
    comparison = build_comparison(PUBLIC_CASE_ID)
    assert comparison is not None
    assert comparison["cryptotrace"]["status"] == "NOT_OBSERVABLE"
    assert comparison["cryptotrace"]["is_demo"] is False
    assert comparison["cryptotrace"]["wallets"] == []
    assert comparison["cryptotrace"]["transaction_references"] == []
    assert all(row["result"] in {"NOT_OBSERVABLE", "NOT_COMPARABLE"} for row in comparison["rows"])
    assert comparison["alignment"]["not_comparable"] == 1
    assert "independently reproduced" in comparison["limitations"]
    combined = " ".join(row["cryptotrace"] for row in comparison["rows"])
    assert "synthetic investigation was run" in combined
    assert "CryptoTrace froze" not in combined


def test_comparison_classifier_preserves_match_partial_and_action_distinction():
    assert classify_comparison("documented", "detected") == "MATCH"
    assert classify_comparison("partially_documented", "partially_observable") == "PARTIAL_MATCH"
    assert classify_comparison("documented", "not_observable") == "NOT_OBSERVABLE"
    assert classify_comparison("documented", "prepared", external_action=True) == "NOT_COMPARABLE"


def test_unknown_public_case_is_not_available():
    assert get_public_case("not-a-real-public-case") is None
    assert build_comparison("not-a-real-public-case") is None


def test_public_case_api_is_investigator_only_and_preserves_provenance():
    with TestClient(app) as client:
        assert client.get("/api/v1/public-cases").status_code == 401
        reporter_login = client.post(
            "/api/v1/auth/login",
            json={"username": "reporter", "password": "report123"},
        )
        reporter = {"Authorization": f"Bearer {reporter_login.json()['access_token']}"}
        assert client.get("/api/v1/public-cases", headers=reporter).status_code == 403

        investigator_login = client.post(
            "/api/v1/auth/login",
            json={"username": "investigator", "password": "investigate123"},
        )
        investigator = {"Authorization": f"Bearer {investigator_login.json()['access_token']}"}
        response = client.get(f"/api/v1/public-cases/{PUBLIC_CASE_ID}/comparison", headers=investigator)
        assert response.status_code == 200
        data = response.json()
        assert data["case"]["source_url"] == SOURCE_URL
        assert data["case"]["publicly_disclosed_wallets"] == []
        assert data["cryptotrace"]["status"] == "NOT_OBSERVABLE"

        listed = client.get("/api/v1/public-cases", headers=investigator)
        assert listed.status_code == 200
        listed_ids = {item["case_id"] for item in listed.json()}
        assert {PUBLIC_CASE_ID, ANALYZABLE_PUBLIC_CASE_ID}.issubset(listed_ids)
