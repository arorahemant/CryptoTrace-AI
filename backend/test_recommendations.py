"""Regression tests for deterministic investigator recommendations."""
from pathlib import Path

import requests


BASE = "http://127.0.0.1:8000/api/v1"
ROOT = Path(__file__).resolve().parent


def _login(username: str, password: str) -> str:
    response = requests.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=10)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_recommendations_are_grounded_ordered_and_duplicate_action_suppressed():
    token = _login("investigator", "investigate123")
    headers = _headers(token)
    created = requests.post(
        f"{BASE}/cases",
        headers=headers,
        json={"title": "Recommendation demo", "reported_wallet": "0xReported001", "blockchain": "demo", "description": "Controlled demo case"},
        timeout=10,
    )
    assert created.status_code == 200, created.text
    case_id = created.json()["id"]
    before_investigation = requests.get(f"{BASE}/cases/{case_id}/recommendations", headers=headers, timeout=10)
    assert before_investigation.status_code == 200, before_investigation.text
    assert before_investigation.json()["recommendations"] == []
    investigated = requests.post(f"{BASE}/cases/{case_id}/investigate", headers=headers, json={"max_hops": 5}, timeout=30)
    assert investigated.status_code == 200, investigated.text

    response = requests.get(f"{BASE}/cases/{case_id}/recommendations", headers=headers, timeout=10)
    assert response.status_code == 200, response.text
    recommendations = response.json()["recommendations"]
    readiness = requests.get(f"{BASE}/cases/{case_id}/action-readiness", headers=headers, timeout=10)
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["attribution_status"] == "likely_inferred"
    assert readiness.json()["attribution_provenance"] == "demo_intelligence"
    attribution_recommendation = next(item for item in recommendations if item["type"] == "review_destination_attribution")
    assert "inferred" in attribution_recommendation["factual_reason"].lower()
    repeat = requests.get(f"{BASE}/cases/{case_id}/recommendations", headers=headers, timeout=10)
    assert repeat.status_code == 200, repeat.text
    repeated_recommendations = repeat.json()["recommendations"]
    assert repeated_recommendations == recommendations
    assert recommendations
    assert len(recommendations) <= 5
    assert [item["priority"] for item in recommendations] == sorted(
        [item["priority"] for item in recommendations], key={"high": 0, "medium": 1, "low": 2}.get
    )
    for item in recommendations:
        assert item["case_id"] == case_id
        assert item["factual_reason"]
        assert item["deterministic_source"]
        assert item["evidence_ids"] or item["transaction_hashes"]

    types = {item["type"] for item in recommendations}
    assert "review_highest_value_intermediary" in types
    assert "inspect_strongest_finding" in types
    assert "review_destination_attribution" in types
    assert "prepare_asset_action_request" in types

    action = next(item for item in recommendations if item["type"] == "prepare_asset_action_request")
    created_request = requests.post(
        f"{BASE}/cases/{case_id}/action-requests",
        headers=headers,
        json={
            "target_wallet": action["target_wallet"],
            "action_type": "preservation_request",
            "evidence_ids": action["evidence_ids"],
            "finding_ids": action["finding_ids"],
        },
        timeout=10,
    )
    assert created_request.status_code == 200, created_request.text
    after = requests.get(f"{BASE}/cases/{case_id}/recommendations", headers=headers, timeout=10)
    assert after.status_code == 200, after.text
    assert "prepare_asset_action_request" not in {item["type"] for item in after.json()["recommendations"]}


def test_recommendations_enforce_reporter_and_idor_boundaries():
    investigator_token = _login("investigator", "investigate123")
    created = requests.post(
        f"{BASE}/cases",
        headers=_headers(investigator_token),
        json={"title": "Owned recommendation case", "reported_wallet": "0xReported001", "blockchain": "demo"},
        timeout=10,
    )
    assert created.status_code == 200, created.text
    case_id = created.json()["id"]

    reporter_login = requests.post(f"{BASE}/auth/login", json={"username": "reporter", "password": "report123"}, timeout=10)
    assert reporter_login.status_code == 200, reporter_login.text
    reporter_token = reporter_login.json()["access_token"]
    reporter = requests.get(f"{BASE}/cases/{case_id}/recommendations", headers=_headers(reporter_token), timeout=10)
    assert reporter.status_code == 403

    other_case = requests.post(
        f"{BASE}/cases",
        headers=_headers(_login("supervisor", "supervisor123")),
        json={"title": "Other recommendation case", "reported_wallet": "0xReported001", "blockchain": "demo"},
        timeout=10,
    )
    assert other_case.status_code == 200, other_case.text
    # A normal investigator cannot enumerate a case owned by another investigator.
    idor = requests.get(f"{BASE}/cases/{other_case.json()['id']}/recommendations", headers=_headers(investigator_token), timeout=10)
    assert idor.status_code == 404

    unauthenticated = requests.get(f"{BASE}/cases/{case_id}/recommendations", timeout=10)
    assert unauthenticated.status_code == 401
