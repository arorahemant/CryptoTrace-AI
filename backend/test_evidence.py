"""Executable evidence persistence check against a running local API."""
import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def test_save_evidence_round_trip():
    login = httpx.post(f"{BASE}/auth/login", json={"username": "investigator", "password": "investigate123"})
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    case = httpx.post(f"{BASE}/cases", headers=headers, json={"title": "Evidence save test", "reported_wallet": "0xReported001", "blockchain": "demo"})
    case.raise_for_status()
    case_id = case.json()["id"]
    investigation = httpx.post(f"{BASE}/cases/{case_id}/investigate", headers=headers, json={})
    investigation.raise_for_status()
    tx = httpx.get(f"{BASE}/cases/{case_id}/transactions", headers=headers).json()["transactions"][0]
    payload = {
        "evidence_type": "transaction",
        "title": "Investigator bookmark",
        "description": "Observed transaction selected for follow-up.",
        "reason": "Supports the traced money trail.",
        "transaction_hash": tx["hash"],
        "wallet_address": tx["to_address"],
        "source": "investigator",
    }
    saved = httpx.post(f"{BASE}/cases/{case_id}/evidence", headers=headers, json=payload)
    saved.raise_for_status()
    body = saved.json()
    assert body["is_bookmarked"] is True
    assert body["transaction_hash"] == tx["hash"]
    listed = httpx.get(f"{BASE}/cases/{case_id}/evidence", headers=headers)
    listed.raise_for_status()
    evidence = listed.json()["evidence"]
    assert any(item["id"] == body["id"] for item in evidence)

    findings_response = httpx.get(f"{BASE}/cases/{case_id}/findings", headers=headers)
    findings_response.raise_for_status()
    finding_ids = {item["id"] for item in findings_response.json()["findings"]}
    generated_pattern_evidence = [item for item in evidence if item["evidence_type"] == "pattern"]
    assert generated_pattern_evidence
    assert all(item["finding_id"] in finding_ids for item in generated_pattern_evidence)
    assert all(item["transaction_hash"] for item in generated_pattern_evidence)

    off_case_wallet = httpx.post(
        f"{BASE}/cases/{case_id}/evidence",
        headers=headers,
        json={
            "evidence_type": "transaction",
            "title": "Invalid wallet bookmark",
            "description": "This must not be persisted.",
            "transaction_hash": tx["hash"],
            "wallet_address": "0xNotPartOfThisCase",
        },
    )
    assert off_case_wallet.status_code == 400
