"""Canonical attribution status and provenance normalization."""
from typing import Any, Protocol
from dataclasses import dataclass
from datetime import datetime, timezone


KNOWN_VERIFIED = "known_verified"
LIKELY_INFERRED = "likely_inferred"
UNKNOWN = "unknown"

DEMO_INTELLIGENCE = "demo_intelligence"
TRUSTED_EXTERNAL_SOURCE = "trusted_external_source"
INSTITUTIONAL_SOURCE = "institutional_source"
ANALYTICAL_INFERENCE = "analytical_inference"
UNKNOWN_PROVENANCE = "unknown"


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value or "").lower()


def normalize_attribution(record: Any) -> dict[str, Any]:
    """Return one honest attribution shape for DB rows and provider dicts."""
    if isinstance(record, dict):
        get = record.get
    else:
        get = lambda key, default=None: getattr(record, key, default)

    raw_get = get
    def get(key, default=None):
        value = raw_get(key, default)
        if key in {'supporting_evidence_ids', 'supporting_transaction_hashes'}:
            return [v for v in value[:1000] if isinstance(v, str) and len(v) <= 255] if isinstance(value, list) else []
        if key == 'verified_at' and value:
            try:
                parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
                if not isinstance(parsed, datetime) or parsed.replace(tzinfo=parsed.tzinfo or timezone.utc) > datetime.now(timezone.utc):
                    return None
                return parsed.isoformat()
            except (ValueError, TypeError):
                return None
        if key in {'entity_name', 'entity_type', 'source', 'source_reference', 'supporting_evidence', 'reasoning'}:
            return value[:2000] if isinstance(value, str) else default
        return value

    confidence = _value(get("confidence", "unknown"))
    provenance = _value(get("provenance", "")) or (
        DEMO_INTELLIGENCE if _value(get("source", "")) == DEMO_INTELLIGENCE else UNKNOWN_PROVENANCE
    )
    raw_status = _value(get("attribution_status", ""))
    if raw_status in {KNOWN_VERIFIED, LIKELY_INFERRED, UNKNOWN}:
        status = raw_status
    elif confidence == "known" and provenance in {TRUSTED_EXTERNAL_SOURCE, INSTITUTIONAL_SOURCE}:
        status = KNOWN_VERIFIED
    elif confidence == "likely" or provenance in {DEMO_INTELLIGENCE, ANALYTICAL_INFERENCE}:
        status = LIKELY_INFERRED
    else:
        status = UNKNOWN

    if status == KNOWN_VERIFIED and provenance not in {TRUSTED_EXTERNAL_SOURCE, INSTITUTIONAL_SOURCE}:
        status = LIKELY_INFERRED
    if status == KNOWN_VERIFIED and not (get("source_reference") and get("verified_at") and (get("supporting_evidence_ids") or get("supporting_transaction_hashes"))):
        status = LIKELY_INFERRED
    if not get('entity_name'):
        status = UNKNOWN
    if status == UNKNOWN:
        entity_name = None
    else:
        entity_name = get("entity_name")

    return {
        "entity_name": entity_name,
        "entity_type": get("entity_type") if status != UNKNOWN else None,
        "attribution_type": "verified" if status == KNOWN_VERIFIED else "inferred" if status == LIKELY_INFERRED else "unknown",
        "confidence": "known" if status == KNOWN_VERIFIED else "likely" if status == LIKELY_INFERRED else "unknown",
        "attribution_status": status,
        "provenance": provenance,
        "source": get("source") or "unknown",
        "source_reference": get("source_reference") or ("CryptoTrace Demo Intelligence" if provenance == DEMO_INTELLIGENCE else None),
        "supporting_evidence": get("supporting_evidence"),
        "reasoning": get("reasoning") or get("supporting_evidence") if status != UNKNOWN else "Attribution is unavailable or insufficiently supported.",
        "supporting_evidence_ids": get("supporting_evidence_ids") or [],
        "supporting_transaction_hashes": get("supporting_transaction_hashes") or [],
        "verified_at": get("verified_at") if status == KNOWN_VERIFIED else None,
    }


@dataclass(frozen=True)
class AttributionScope:
    """Allowlisted observation context. No complaint, victim, user or credentials."""
    network: str
    run_id: str | None
    addresses: frozenset[str]
    transaction_hashes: dict[str, set[str]]
    evidence_ids: dict[str, set[str]]


class AttributionSource(Protocol):
    async def lookup(self, scope: AttributionScope) -> dict[str, dict]: ...


class StoredAttributionSource:
    """Only persisted case intelligence is connected; no external lookups."""
    def __init__(self, rows):
        self.rows = rows

    async def lookup(self, scope):
        result = {}
        for row in self.rows:
            address = row.wallet_address
            if address not in scope.addresses or address in result:
                continue
            data = normalize_attribution(row)
            if scope.network != 'demo' and data['provenance'] not in {TRUSTED_EXTERNAL_SOURCE, INSTITUTIONAL_SOURCE, ANALYTICAL_INFERENCE}:
                data = normalize_attribution({})
            data['supporting_evidence_ids'] = [str(e) for e in data['supporting_evidence_ids'] if str(e) in scope.evidence_ids.get(address, set())]
            data['supporting_transaction_hashes'] = [h for h in data['supporting_transaction_hashes'] if h in scope.transaction_hashes.get(address, set())]
            supported = data['supporting_evidence_ids'] or data['supporting_transaction_hashes']
            # References must resolve to this address in this case/current run.
            if not supported and (scope.network != 'demo' or data['attribution_status'] == KNOWN_VERIFIED):
                data = normalize_attribution({})
            result[address] = data
        return result


async def resolve_attributions(db, case):
    from sqlalchemy import select
    from app.models.models import Wallet, Transaction, Evidence, VASPAttribution
    from app.core.capabilities import current_observation, capability_payload
    if not current_observation(case):
        return {}
    run_id = capability_payload(case)['run_id']
    wallets = (await db.scalars(select(Wallet).where(Wallet.case_id == case.id))).all()
    transactions = (await db.scalars(select(Transaction).where(Transaction.case_id == case.id))).all()
    evidence = (await db.scalars(select(Evidence).where(Evidence.case_id == case.id))).all()
    addresses = frozenset(w.address for w in wallets)
    hashes = {a: {t.hash for t in transactions if a in (t.from_address, t.to_address)} for a in addresses}
    evidence_ids = {a: {str(e.id) for e in evidence if
        (case.blockchain.value == 'demo' or (e.metadata_ or {}).get('run_id') == run_id) and
        (e.wallet_address == a or e.transaction_hash in hashes[a])} for a in addresses}
    rows = (await db.scalars(select(VASPAttribution).where(VASPAttribution.case_id == case.id)
        .order_by(VASPAttribution.created_at.desc(), VASPAttribution.id))).all()
    scope = AttributionScope(case.blockchain.value, run_id, addresses, hashes, evidence_ids)
    return await StoredAttributionSource(rows).lookup(scope)
