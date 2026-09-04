"""Incoming reporter queue, acceptance, ownership, and start workflow checks."""

import asyncio
import uuid

import httpx
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.models import AuditLog


BASE = "http://127.0.0.1:8000/api/v1"


def _login(username: str, password: str) -> dict:
    response = httpx.post(
        f"{BASE}/auth/login",
        json={"username": username, "password": password},
    )
    response.raise_for_status()
    return response.json()


def test_reporter_submission_review_accept_and_demo_start_are_audited():
    reporter = _login("reporter", "report123")
    reporter_headers = {"Authorization": f"Bearer {reporter['access_token']}"}
    suffix = uuid.uuid4().hex[:8]
    submission = httpx.post(
        f"{BASE}/reporter/submissions",
        headers=reporter_headers,
        json={
            "title": f"Incoming demo report {suffix}",
            "reported_wallet": "0xReported001",
            "blockchain": "demo",
            "asset": "ETH",
            "description": "Reporter supplied incident summary for queue review.",
        },
    )
    submission.raise_for_status()
    submission_data = submission.json()

    investigator = _login("investigator", "investigate123")
    investigator_headers = {"Authorization": f"Bearer {investigator['access_token']}"}
    queue = httpx.get(f"{BASE}/reporter/submissions/review", headers=investigator_headers)
    queue.raise_for_status()
    queued = next(item for item in queue.json()["submissions"] if item["id"] == submission_data["id"])
    assert queued["status"] == "report_received"
    assert queued["blockchain"] == "demo"
    assert queued["asset"] == "ETH"

    review = httpx.get(
        f"{BASE}/reporter/submissions/{submission_data['id']}/review",
        headers=investigator_headers,
    )
    review.raise_for_status()
    review_data = review.json()
    assert review_data["status"] == "new"
    assert review_data["description"] == "Reporter supplied incident summary for queue review."
    assert httpx.get(
        f"{BASE}/reporter/submissions/{submission_data['id']}/review",
        headers=reporter_headers,
    ).status_code == 403

    accepted = httpx.post(
        f"{BASE}/reporter/submissions/{submission_data['id']}/accept",
        headers=investigator_headers,
    )
    accepted.raise_for_status()
    accepted_data = accepted.json()
    assert accepted_data["status"] == "accepted"
    assert accepted_data["case_status"] == "accepted"
    case_id = accepted_data["case_id"]
    assert httpx.post(
        f"{BASE}/reporter/submissions/{submission_data['id']}/accept",
        headers=investigator_headers,
    ).status_code == 409

    case = httpx.get(f"{BASE}/cases/{case_id}", headers=investigator_headers)
    case.raise_for_status()
    case_data = case.json()
    assert case_data["reported_wallet"] == "0xReported001"
    assert case_data["blockchain"] == "demo"
    assert case_data["asset"] == "ETH"
    assert case_data["source_submission_reference"] == submission_data["reference_number"]
    assert case_data["status"] == "accepted"

    started = httpx.post(f"{BASE}/cases/{case_id}/investigate", headers=investigator_headers, json={}, timeout=30)
    started.raise_for_status()
    repeated = httpx.post(f"{BASE}/cases/{case_id}/investigate", headers=investigator_headers, json={}, timeout=30)
    repeated.raise_for_status()

    audit = httpx.get(f"{BASE}/cases/{case_id}/audit", headers=investigator_headers)
    audit.raise_for_status()
    actions = {event["action"] for event in audit.json()["events"]}

    async def submission_audit_actions() -> set[str]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AuditLog.action).where(AuditLog.resource_id == submission_data["id"])
            )
            return set(result.scalars().all())

    assert "report_reviewed" in asyncio.run(submission_audit_actions())
    assert {"case_accepted", "investigation_started", "investigation_completed"} <= actions


def test_incoming_queue_and_case_acceptance_remain_investigator_only():
    reporter = _login("reporter", "report123")
    reporter_headers = {"Authorization": f"Bearer {reporter['access_token']}"}
    assert httpx.get(f"{BASE}/reporter/submissions/review", headers=reporter_headers).status_code == 403

    suffix = uuid.uuid4().hex[:8]
    registration = httpx.post(
        f"{BASE}/auth/register",
        json={
            "email": f"queue_{suffix}@example.com",
            "username": f"queue_{suffix}",
            "password": "investigator-test-123",
            "full_name": "Queue Access Tester",
        },
    )
    registration.raise_for_status()
    other = _login(f"queue_{suffix}", "investigator-test-123")
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    submission = httpx.post(
        f"{BASE}/reporter/submissions",
        headers=reporter_headers,
        json={
            "title": f"Ownership queue report {suffix}",
            "reported_wallet": "0xReported001",
            "blockchain": "demo",
            "asset": "ETH",
        },
    )
    submission.raise_for_status()
    submission_id = submission.json()["id"]
    investigator = _login("investigator", "investigate123")
    accepted = httpx.post(
        f"{BASE}/reporter/submissions/{submission_id}/accept",
        headers={"Authorization": f"Bearer {investigator['access_token']}"},
    )
    accepted.raise_for_status()
    case_id = accepted.json()["case_id"]
    assert httpx.get(f"{BASE}/cases/{case_id}", headers=other_headers).status_code in (403, 404)
    assert httpx.get(f"{BASE}/cases/{case_id}/audit", headers=reporter_headers).status_code == 403
