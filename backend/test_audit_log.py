"""Executable audit-event checks against a running local API."""
import asyncio
import httpx
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.models import AuditLog


BASE = "http://127.0.0.1:8000/api/v1"


def test_key_investigator_actions_are_audited():
    login = httpx.post(
        f"{BASE}/auth/login",
        json={"username": "investigator", "password": "investigate123"},
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    case = httpx.post(
        f"{BASE}/cases",
        headers=headers,
        json={"title": "Audit log test", "reported_wallet": "0xReported001", "blockchain": "demo"},
    )
    case.raise_for_status()
    case_id = case.json()["id"]

    httpx.get(f"{BASE}/cases/{case_id}", headers=headers).raise_for_status()
    httpx.post(f"{BASE}/cases/{case_id}/investigate", headers=headers, json={}).raise_for_status()
    tx = httpx.get(f"{BASE}/cases/{case_id}/transactions", headers=headers).json()["transactions"][0]
    evidence = httpx.post(
        f"{BASE}/cases/{case_id}/evidence",
        headers=headers,
        json={
            "evidence_type": "transaction",
            "title": "Audit bookmark",
            "description": "Audit test evidence",
            "transaction_hash": tx["hash"],
            "wallet_address": tx["to_address"],
        },
    )
    evidence.raise_for_status()
    report = httpx.post(f"{BASE}/cases/{case_id}/report", headers=headers)
    report.raise_for_status()

    async def read_actions():
        async with async_session_factory() as db:
            result = await db.execute(
                select(AuditLog.action).where(
                    AuditLog.resource_id.in_([case_id, evidence.json()["id"], report.json()["id"]])
                )
            )
            return {row[0] for row in result.all()}

    actions = asyncio.run(read_actions())
    assert {"case_created", "case_viewed", "investigation_completed", "evidence_saved", "report_generated"} <= actions
