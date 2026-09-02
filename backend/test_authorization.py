"""Executable IDOR/RBAC checks against a running local API.

Run with the backend serving on http://127.0.0.1:8000.
"""
import uuid
import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def login(username: str, password: str) -> str:
    response = httpx.post(f"{BASE}/auth/login", json={"username": username, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]


def test_idor_denied_for_investigator_and_allowed_for_supervisor():
    owner_token = login("investigator", "investigate123")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    case = httpx.post(
        f"{BASE}/cases",
        headers=owner_headers,
        json={"title": "Authorization test", "reported_wallet": "0xReported001", "blockchain": "demo"},
    )
    case.raise_for_status()
    case_id = case.json()["id"]

    username = f"idor_{uuid.uuid4().hex[:10]}"
    register = httpx.post(
        f"{BASE}/auth/register",
        json={"email": f"{username}@example.com", "username": username, "password": "testpass123", "full_name": "IDOR Tester", "role": "admin"},
    )
    register.raise_for_status()
    assert register.json()["role"] == "investigator"
    other_headers = {"Authorization": f"Bearer {login(username, 'testpass123')}"}

    sensitive = [
        ("GET", f"/cases/{case_id}"), ("POST", f"/cases/{case_id}/investigate"),
        ("GET", f"/cases/{case_id}/wallets"), ("GET", f"/cases/{case_id}/transactions"),
        ("GET", f"/cases/{case_id}/graph"), ("GET", f"/cases/{case_id}/fund-flow"),
        ("GET", f"/cases/{case_id}/timeline"), ("GET", f"/cases/{case_id}/findings"),
        ("GET", f"/cases/{case_id}/evidence"), ("POST", f"/cases/{case_id}/replay"),
        ("POST", f"/cases/{case_id}/evidence"),
        ("POST", f"/cases/{case_id}/ai/query"), ("POST", f"/cases/{case_id}/report"),
        ("GET", f"/cases/{case_id}/report"), ("GET", f"/cases/{case_id}/why/0xReported001"),
    ]
    for method, path in sensitive:
        response = httpx.request(
            method, f"{BASE}{path}", headers=other_headers,
            json=(
                {"question": "summary"}
                if path.endswith("ai/query")
                else {"evidence_type": "transaction", "title": "IDOR probe", "description": "unauthorized probe", "reason": "unauthorized"}
                if path.endswith("/evidence") and method == "POST"
                else None
            ),
        )
        assert response.status_code == 404, f"{method} {path}: {response.status_code}"

    supervisor_headers = {"Authorization": f"Bearer {login('supervisor', 'supervisor123')}"}
    assert httpx.get(f"{BASE}/cases/{case_id}", headers=supervisor_headers).status_code == 200
    assert any(item["id"] == case_id for item in httpx.get(f"{BASE}/cases", headers=supervisor_headers).json()["cases"])
    admin_headers = {"Authorization": f"Bearer {login('admin', 'admin123')}"}
    assert httpx.get(f"{BASE}/cases/{case_id}", headers=admin_headers).status_code == 200
    assert any(item["id"] == case_id for item in httpx.get(f"{BASE}/cases", headers=admin_headers).json()["cases"])


def test_unauthenticated_case_access_is_denied():
    response = httpx.get(f"{BASE}/cases")
    assert response.status_code == 401
