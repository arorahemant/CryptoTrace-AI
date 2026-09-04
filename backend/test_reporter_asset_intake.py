"""Reporter network/asset intake and unsupported-analysis safety checks."""

import uuid

import httpx


BASE = "http://127.0.0.1:8000/api/v1"


def _login(username: str, password: str) -> dict:
    response = httpx.post(
        f"{BASE}/auth/login",
        json={"username": username, "password": password},
    )
    response.raise_for_status()
    return response.json()


def test_reporter_accepts_supported_network_asset_pairs_without_fake_analysis():
    reporter = _login("reporter", "report123")
    headers = {"Authorization": f"Bearer {reporter['access_token']}"}
    suffix = uuid.uuid4().hex[:8]
    submissions = [
        ("bitcoin", "BTC", "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"),
        ("ethereum", "USDT", "0x1111111111111111111111111111111111111111"),
        ("tron", "TRX", "TJRabPrwbZy45sbavfcjinPJC18puDgZGL"),
        ("polygon", "USDC", "0x2222222222222222222222222222222222222222"),
        ("demo", "ETH", "0xReported001"),
    ]

    for network, asset, wallet in submissions:
        response = httpx.post(
            f"{BASE}/reporter/submissions",
            headers=headers,
            json={
                "title": f"Network intake {network} {suffix}",
                "reported_wallet": wallet,
                "blockchain": network,
                "asset": asset,
            },
        )
        response.raise_for_status()
        data = response.json()
        assert data["blockchain"] == network
        assert data["asset"] == asset
        if network == "demo":
            assert data["analysis_status"] == "analysis_available"
            assert "deterministic" in data["analysis_message"].lower()
        else:
            assert data["analysis_status"] == "analysis_not_connected"
            assert "not connected" in data["analysis_message"].lower()


def test_reporter_rejects_invalid_asset_network_pair_and_wallet_format():
    reporter = _login("reporter", "report123")
    headers = {"Authorization": f"Bearer {reporter['access_token']}"}
    invalid_asset = httpx.post(
        f"{BASE}/reporter/submissions",
        headers=headers,
        json={
            "title": "Invalid asset pair",
            "reported_wallet": "0x1111111111111111111111111111111111111111",
            "blockchain": "ethereum",
            "asset": "BTC",
        },
    )
    assert invalid_asset.status_code == 400

    invalid_tron = httpx.post(
        f"{BASE}/reporter/submissions",
        headers=headers,
        json={
            "title": "Invalid Tron wallet",
            "reported_wallet": "0x1111111111111111111111111111111111111111",
            "blockchain": "tron",
            "asset": "TRX",
        },
    )
    assert invalid_tron.status_code == 400


def test_investigator_sees_network_asset_and_unsupported_case_cannot_run_demo_analysis():
    reporter = _login("reporter", "report123")
    reporter_headers = {"Authorization": f"Bearer {reporter['access_token']}"}
    suffix = uuid.uuid4().hex[:8]
    submission = httpx.post(
        f"{BASE}/reporter/submissions",
        headers=reporter_headers,
        json={
            "title": f"Investigator visibility {suffix}",
            "reported_wallet": "0x3333333333333333333333333333333333333333",
            "blockchain": "ethereum",
            "asset": "ETH",
        },
    )
    submission.raise_for_status()
    submission_data = submission.json()
    assert httpx.get(
        f"{BASE}/reporter/submissions/{submission_data['id']}",
        headers=reporter_headers,
    ).json()["asset"] == "ETH"

    investigator = _login("investigator", "investigate123")
    investigator_headers = {"Authorization": f"Bearer {investigator['access_token']}"}
    review = httpx.get(
        f"{BASE}/reporter/submissions/review",
        headers=investigator_headers,
    )
    review.raise_for_status()
    reviewed = next(
        item for item in review.json()["submissions"]
        if item["id"] == submission_data["id"]
    )
    assert reviewed["blockchain"] == "ethereum"
    assert reviewed["asset"] == "ETH"
    assert reviewed["analysis_status"] == "analysis_not_connected"

    assignment = httpx.post(
        f"{BASE}/reporter/submissions/{submission_data['id']}/assign",
        headers=investigator_headers,
    )
    assignment.raise_for_status()
    case_id = assignment.json()["case_id"]
    case = httpx.get(f"{BASE}/cases/{case_id}", headers=investigator_headers)
    case.raise_for_status()
    assert case.json()["asset"] == "ETH"
    assert case.json()["analysis_status"] == "analysis_not_connected"

    investigation = httpx.post(
        f"{BASE}/cases/{case_id}/investigate",
        headers=investigator_headers,
        json={},
    )
    assert investigation.status_code == 409
    assert "not connected" in investigation.json()["detail"].lower()

    assert httpx.get(
        f"{BASE}/reporter/submissions/review",
        headers=reporter_headers,
    ).status_code == 403
