"""Canonical attribution status and provenance normalization."""
from typing import Any


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
    if status == UNKNOWN:
        entity_name = None
    else:
        entity_name = get("entity_name")

    return {
        "entity_name": entity_name,
        "entity_type": get("entity_type"),
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
