"""Reporter ownership, role separation, and public-profile checks."""
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


def test_reporter_is_case_scoped_and_investigator_details_require_approval():
    reporter_login = _login("reporter", "report123")
    assert reporter_login["user"]["role"] == "reporter"
    reporter_headers = {"Authorization": f"Bearer {reporter_login['access_token']}"}

    investigator_login = _login("investigator", "investigate123")
    investigator_headers = {"Authorization": f"Bearer {investigator_login['access_token']}"}

    assert httpx.get(f"{BASE}/cases", headers=reporter_headers).status_code == 403
    assert httpx.get(f"{BASE}/reporter/submissions", headers=investigator_headers).status_code == 403
    assert httpx.get(f"{BASE}/reporter/submissions").status_code == 401
    assert httpx.get(
        f"{BASE}/auth/me/public-profile", headers=reporter_headers
    ).status_code == 403

    submission = httpx.post(
        f"{BASE}/reporter/submissions",
        headers=reporter_headers,
        json={
            "title": "Reporter ownership test",
            "reported_wallet": "0xReported001",
            "blockchain": "demo",
            "description": "Deterministic reporter access test.",
        },
    )
    submission.raise_for_status()
    submission_data = submission.json()
    submission_id = submission_data["id"]
    assert submission_data["status"] == "report_received"
    assert submission_data["status_label"] == "Report received"
    assert submission_data["assigned_investigator"] is None
    assert submission_data["reference_number"].startswith("CTR-")

    own_list = httpx.get(f"{BASE}/reporter/submissions", headers=reporter_headers)
    own_list.raise_for_status()
    assert submission_id in {item["id"] for item in own_list.json()}

    suffix = uuid.uuid4().hex[:10]
    other_username = f"reporter_{suffix}"
    other_registration = httpx.post(
        f"{BASE}/auth/reporter/register",
        json={
            "email": f"{other_username}@example.com",
            "username": other_username,
            "password": "reporter-test-123",
            "full_name": "Reporter Access Tester",
        },
    )
    other_registration.raise_for_status()
    assert other_registration.json()["role"] == "reporter"
    other_login = _login(other_username, "reporter-test-123")
    other_headers = {"Authorization": f"Bearer {other_login['access_token']}"}
    assert httpx.get(
        f"{BASE}/reporter/submissions/{submission_id}", headers=other_headers
    ).status_code == 404
    assert submission_id not in {
        item["id"]
        for item in httpx.get(
            f"{BASE}/reporter/submissions", headers=other_headers
        ).json()
    }

    review = httpx.get(
        f"{BASE}/reporter/submissions/review", headers=investigator_headers
    )
    review.raise_for_status()
    assert submission_id in {item["id"] for item in review.json()["submissions"]}

    assignment = httpx.post(
        f"{BASE}/reporter/submissions/{submission_id}/assign",
        headers=investigator_headers,
    )
    assignment.raise_for_status()
    case_id = assignment.json()["case_id"]
    assert httpx.get(f"{BASE}/cases/{case_id}", headers=investigator_headers).status_code == 200
    assert httpx.get(f"{BASE}/cases/{case_id}", headers=reporter_headers).status_code == 403
    assert httpx.post(
        f"{BASE}/reporter/submissions/{submission_id}/assign",
        headers=investigator_headers,
    ).status_code == 409

    assigned_status = httpx.get(
        f"{BASE}/reporter/submissions/{submission_id}", headers=reporter_headers
    )
    assigned_status.raise_for_status()
    assert assigned_status.json()["status"] == "under_investigation"
    assert assigned_status.json()["assigned_investigator"] is None

    public_profile = {
        "display_name": "Investigator Demo Public",
        "role_title": "Case Investigator",
        "is_reporter_visible": True,
    }
    approved = httpx.put(
        f"{BASE}/auth/me/public-profile",
        headers=investigator_headers,
        json=public_profile,
    )
    approved.raise_for_status()
    persisted_profile = httpx.get(
        f"{BASE}/auth/me/public-profile", headers=investigator_headers
    )
    persisted_profile.raise_for_status()
    assert persisted_profile.json()["display_name"] == public_profile["display_name"]
    assert persisted_profile.json()["is_reporter_visible"] is True
    visible_status = httpx.get(
        f"{BASE}/reporter/submissions/{submission_id}", headers=reporter_headers
    )
    visible_status.raise_for_status()
    assert visible_status.json()["assigned_investigator"] == {
        "display_name": public_profile["display_name"],
        "role_title": public_profile["role_title"],
    }

    public_profile["is_reporter_visible"] = False
    httpx.put(
        f"{BASE}/auth/me/public-profile",
        headers=investigator_headers,
        json=public_profile,
    ).raise_for_status()
    hidden_status = httpx.get(
        f"{BASE}/reporter/submissions/{submission_id}", headers=reporter_headers
    )
    assert hidden_status.json()["assigned_investigator"] is None
