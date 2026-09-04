"""Feature 1 integration coverage for readiness and external action requests."""
import uuid

import httpx


BASE = "http://127.0.0.1:8000/api/v1"


def _login(username: str, password: str) -> dict:
    response = httpx.post(f"{BASE}/auth/login", json={"username": username, "password": password})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_asset_action_workflow_is_case_scoped_and_transition_safe():
    investigator = _login("investigator", "investigate123")
    case = httpx.post(
        f"{BASE}/cases",
        headers=investigator,
        json={"title": "Feature 1 request test", "reported_wallet": "0xReported001", "blockchain": "demo"},
    )
    case.raise_for_status()
    case_id = case.json()["id"]
    investigation = httpx.post(f"{BASE}/cases/{case_id}/investigate", headers=investigator, json={})
    investigation.raise_for_status()

    readiness = httpx.get(f"{BASE}/cases/{case_id}/action-readiness", headers=investigator)
    readiness.raise_for_status()
    readiness_data = readiness.json()
    assert readiness_data["destination_wallet"] == "0xExchang009"
    assert readiness_data["attribution_status"] == "likely_inferred"
    assert all("complete" in check for check in readiness_data["checks"])
    assert readiness_data["evidence_ids"]

    request_payload = {
        "target_wallet": readiness_data["destination_wallet"],
        "action_type": "preservation_request",
        "evidence_ids": readiness_data["evidence_ids"][:1],
        "finding_ids": readiness_data["finding_ids"],
    }
    created = httpx.post(f"{BASE}/cases/{case_id}/action-requests", headers=investigator, json=request_payload)
    created.raise_for_status()
    item = created.json()
    request_id = item["id"]
    assert item["status"] == "draft"
    assert item["evidence_ids"] == request_payload["evidence_ids"]

    duplicate = httpx.post(f"{BASE}/cases/{case_id}/action-requests", headers=investigator, json=request_payload)
    duplicate.raise_for_status()
    assert duplicate.json()["id"] == request_id

    invalid = httpx.patch(
        f"{BASE}/cases/{case_id}/action-requests/{request_id}/status",
        headers=investigator,
        json={"status": "actioned"},
    )
    assert invalid.status_code == 409

    prepared = httpx.post(f"{BASE}/cases/{case_id}/action-requests/{request_id}/prepare", headers=investigator)
    prepared.raise_for_status()
    assert prepared.json()["status"] == "prepared"
    for next_status in ("submitted", "acknowledged", "actioned"):
        response = httpx.patch(
            f"{BASE}/cases/{case_id}/action-requests/{request_id}/status",
            headers=investigator,
            json={"status": next_status},
        )
        response.raise_for_status()
        assert response.json()["status"] == next_status

    listed = httpx.get(f"{BASE}/cases/{case_id}/action-requests", headers=investigator)
    listed.raise_for_status()
    assert any(row["id"] == request_id for row in listed.json())

    audit = httpx.get(f"{BASE}/cases/{case_id}/audit", headers=investigator)
    audit.raise_for_status()
    actions = {event["action"] for event in audit.json()["events"]}
    assert {"request_created", "request_prepared", "request_submitted", "request_acknowledged", "request_actioned"} <= actions


def test_asset_action_authorization_and_reference_validation():
    investigator = _login("investigator", "investigate123")
    reporter = _login("reporter", "report123")
    case = httpx.post(
        f"{BASE}/cases",
        headers=investigator,
        json={"title": "Feature 1 authorization test", "reported_wallet": "0xReported001", "blockchain": "demo"},
    )
    case.raise_for_status()
    case_id = case.json()["id"]

    assert httpx.get(f"{BASE}/cases/{case_id}/action-readiness", headers=reporter).status_code == 403
    assert httpx.get(f"{BASE}/cases/{case_id}/action-requests", headers={}).status_code == 401

    response = httpx.post(
        f"{BASE}/cases/{case_id}/action-requests",
        headers=investigator,
        json={
            "target_wallet": "0xNotInCase",
            "action_type": "freeze_request",
            "evidence_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 422

    source = open("app/core/security.py", encoding="utf-8").read()
    assert "encrypt" not in source.lower()
    assert "SECRET_KEY" in source
