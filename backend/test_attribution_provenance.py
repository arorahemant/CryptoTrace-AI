"""Attribution honesty and provenance regression tests."""
from app.services.attribution_service import normalize_attribution


def test_known_verified_requires_authoritative_provenance():
    verified = normalize_attribution({
        "entity_name": "Authoritative VASP",
        "confidence": "known",
        "attribution_status": "known_verified",
        "provenance": "trusted_external_source",
        "source_reference": "trusted-provider-record-1",
        "reasoning": "Matched authoritative address intelligence record.",
    })
    assert verified["attribution_status"] == "known_verified"
    assert verified["attribution_type"] == "verified"

    demo_upgrade_attempt = normalize_attribution({
        "entity_name": "DemoExchange",
        "confidence": "known",
        "attribution_status": "known_verified",
        "provenance": "demo_intelligence",
    })
    assert demo_upgrade_attempt["attribution_status"] == "likely_inferred"


def test_likely_and_unknown_attributions_keep_reason_and_safe_identity():
    likely = normalize_attribution({
        "entity_name": "DemoExchange (Simulated)",
        "confidence": "likely",
        "source": "demo_intelligence",
        "provenance": "demo_intelligence",
        "reasoning": "Observed destination relationship in the deterministic investigation dataset.",
    })
    assert likely["attribution_status"] == "likely_inferred"
    assert likely["source_reference"] == "CryptoTrace Demo Intelligence"
    assert likely["reasoning"].startswith("Observed destination relationship")

    unknown = normalize_attribution({
        "entity_name": "Unconfirmed Label",
        "confidence": "unknown",
        "provenance": "unknown",
    })
    assert unknown["attribution_status"] == "unknown"
    assert unknown["entity_name"] is None
    assert unknown["reasoning"] == "Attribution is unavailable or insufficiently supported."
