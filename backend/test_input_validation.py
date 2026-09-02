"""Executable wallet-intake validation checks against a running API."""

import httpx


BASE = "http://127.0.0.1:8000/api/v1"


def _headers() -> dict[str, str]:
    response = httpx.post(
        f"{BASE}/auth/login",
        json={"username": "investigator", "password": "investigate123"},
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_wallet_format_is_chain_aware():
    headers = _headers()
    invalid_demo = httpx.post(
        f"{BASE}/cases",
        headers=headers,
        json={"title": "Invalid demo wallet", "reported_wallet": "wallet with spaces", "blockchain": "demo"},
    )
    assert invalid_demo.status_code == 400

    invalid_evm = httpx.post(
        f"{BASE}/cases",
        headers=headers,
        json={"title": "Invalid EVM wallet", "reported_wallet": "0x1234567890", "blockchain": "ethereum"},
    )
    assert invalid_evm.status_code == 400

    valid_demo = httpx.post(
        f"{BASE}/cases",
        headers=headers,
        json={"title": "Valid demo wallet", "reported_wallet": "0xReported001", "blockchain": "demo"},
    )
    assert valid_demo.status_code == 200
