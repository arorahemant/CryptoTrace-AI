"""Quick P0 endpoint integration test for a running local API."""

import httpx


BASE = "http://127.0.0.1:8000/api/v1"


def test_p0_endpoint_smoke():
    """Exercise the minimum investigator journey with an isolated demo case."""
    login = httpx.post(
        f"{BASE}/auth/login",
        json={"username": "investigator", "password": "investigate123"},
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    case = httpx.post(
        f"{BASE}/cases",
        headers=headers,
        json={
            "title": "P0 smoke validation",
            "reported_wallet": "0xReported001",
            "blockchain": "demo",
        },
    )
    case.raise_for_status()
    case_id = case.json()["id"]

    investigation = httpx.post(
        f"{BASE}/cases/{case_id}/investigate",
        headers=headers,
        json={},
        timeout=30,
    )
    investigation.raise_for_status()
    assert investigation.json()["case_id"] == case_id

    why = httpx.get(
        f"{BASE}/cases/{case_id}/why/0xIntermed002", headers=headers
    )
    why.raise_for_status()
    assert why.json()["reasons"]

    ai = httpx.post(
        f"{BASE}/cases/{case_id}/ai/query",
        json={"question": "Where did the money go?"},
        headers=headers,
        timeout=15,
    )
    ai.raise_for_status()
    assert ai.json()["grounded"] is True
    assert ai.json()["sources"]

    report = httpx.post(
        f"{BASE}/cases/{case_id}/report", headers=headers, timeout=15
    )
    report.raise_for_status()
    assert report.json()["sections"]

    replay = httpx.post(
        f"{BASE}/cases/{case_id}/replay", headers=headers, timeout=15
    )
    replay.raise_for_status()
    replay_data = replay.json()
    assert replay_data["events"]
    assert replay_data["events"][0]["transaction_hash"]

    graph = httpx.get(f"{BASE}/cases/{case_id}/graph", headers=headers)
    graph.raise_for_status()
    assert graph.json()["nodes"]
    assert graph.json()["edges"]

    timeline = httpx.get(f"{BASE}/cases/{case_id}/timeline", headers=headers)
    timeline.raise_for_status()
    assert timeline.json()["events"]


if __name__ == "__main__":
    test_p0_endpoint_smoke()
    print("=== ALL P0 ENDPOINTS TESTED ===")
