"""Source-backed public case references and bounded comparison logic.

This module intentionally contains reference material only.  It does not
turn a public case document into a CryptoTrace investigation when the source
does not publish an analyzable wallet and transaction set.
"""
from copy import deepcopy
from typing import Any


PUBLIC_CASE_ID = "hyderabad-task-investment-fraud-2023"
SOURCE_URL = "https://www.hyderabadpolice.gov.in/assets/news/2023/07july/22072023.pdf"
ANALYZABLE_PUBLIC_CASE_ID = "north-texas-chaos-ransomware-seizure-2025"
ANALYZABLE_SOURCE_URL = "https://www.justice.gov/usao-ndtx/pr/united-states-files-civil-complaint-northern-district-texas-seeking-forfeiture-over-17"
ANALYZABLE_WALLET = "bc1q5d8af0crjhlnepjq08muhh55899rf2ktye3sxd"

_PUBLIC_CASE = {
    "case_id": PUBLIC_CASE_ID,
    "title": "Hyderabad task-based investment fraud",
    "case_label": "PUBLIC CASE REFERENCE",
    "source_authority": "Hyderabad City Police",
    "source_type": "Official government document",
    "source_url": SOURCE_URL,
    "jurisdiction": "Hyderabad, India",
    "publication_date": "July 2023",
    "blockchain": "TRON",
    "network_note": "The document mentions a Tron wallet, but does not publish its exact address.",
    "asset": "USDT / TRON",
    "publicly_disclosed_wallets": [],
    "wallet_disclosure_note": "NOT PUBLICLY DISCLOSED",
    "disclosed_transaction_references": [],
    "transaction_disclosure_note": "NOT PUBLICLY DISCLOSED",
    "provenance": "PUBLIC_CASE_REFERENCE",
    "analysis_availability": "NOT OBSERVABLE WITH CURRENT PROVIDER",
    "analysis_note": "The source has no public wallet or transaction identifier that the current provider can analyze.",
    "facts": [
        {
            "fact_id": "victim_loss",
            "label": "Victim-reported loss",
            "value": "₹28 lakhs",
            "source_locator": "Official document, page 1",
        },
        {
            "fact_id": "fund_movement",
            "label": "Documented fund movement",
            "value": "The document states that the lost amount was transferred to six accounts and later used to purchase cryptocurrency in Dubai.",
            "source_locator": "Official document, pages 1–2",
        },
        {
            "fact_id": "crypto_conversion",
            "label": "Documented crypto conversion",
            "value": "The document describes conversion of fraud proceeds into USDT and mentions a Tron coin wallet.",
            "source_locator": "Official document, page 2",
        },
        {
            "fact_id": "documented_outcome",
            "label": "Documented outcome",
            "value": "The document reports ₹10,53,89,943 frozen in bank accounts.",
            "source_locator": "Official document, page 3",
        },
    ],
    "outcome_note": "The published outcome concerns accounts described in the document; it is not treated as a CryptoTrace action.",
}

_ANALYZABLE_PUBLIC_CASE = {
    "case_id": ANALYZABLE_PUBLIC_CASE_ID,
    "title": "Northern District of Texas cryptocurrency seizure linked to ransomware allegations",
    "case_label": "PUBLIC CASE REFERENCE",
    "source_authority": "U.S. Department of Justice — U.S. Attorney's Office, Northern District of Texas",
    "source_type": "Official government press release",
    "source_url": ANALYZABLE_SOURCE_URL,
    "jurisdiction": "Northern District of Texas, United States",
    "publication_date": "July 28, 2025",
    "blockchain": "BITCOIN",
    "network_note": "The official release explicitly identifies a Bitcoin address and the seizure date and amount.",
    "asset": "BTC",
    "publicly_disclosed_wallets": [ANALYZABLE_WALLET],
    "wallet_disclosure_note": "Address identified in the public case record; it is not labeled as a fraud wallet by CryptoTrace.",
    "disclosed_transaction_references": [],
    "transaction_disclosure_note": "NOT PUBLICLY DISCLOSED — the official release does not publish a transaction hash.",
    "provenance": "PUBLIC_CASE_REFERENCE",
    "analysis_availability": "NOT OBSERVABLE WITH CURRENT PROVIDER",
    "analysis_note": "Public on-chain input data is available, but the current analytics provider is deterministic DemoProvider and has no live Bitcoin data source.",
    "facts": [
        {
            "fact_id": "seized_amount",
            "label": "Documented seized amount",
            "value": "20.2891382 BTC was seized from the identified Bitcoin address.",
            "source_locator": "Official press release, paragraph 2",
        },
        {
            "fact_id": "seizure_date",
            "label": "Documented seizure date",
            "value": "The release states that the cryptocurrency was seized on April 15, 2025.",
            "source_locator": "Official press release, paragraph 2",
        },
        {
            "fact_id": "address_context",
            "label": "Address context",
            "value": "The release says the cryptocurrency was traced to an address allegedly associated with a member of the Chaos ransomware group.",
            "source_locator": "Official press release, paragraph 3",
        },
        {
            "fact_id": "documented_outcome",
            "label": "Documented outcome",
            "value": "Dallas FBI executed the cryptocurrency seizure and the United States filed a civil forfeiture complaint; the stated allegations are not treated as a CryptoTrace finding.",
            "source_locator": "Official press release, paragraphs 1 and 3",
        },
    ],
    "outcome_note": "The source documents an external law-enforcement seizure and civil forfeiture proceeding. CryptoTrace does not claim to have performed or reproduced that action.",
}

_PUBLIC_CASES = {
    PUBLIC_CASE_ID: _PUBLIC_CASE,
    ANALYZABLE_PUBLIC_CASE_ID: _ANALYZABLE_PUBLIC_CASE,
}


def list_public_cases() -> list[dict[str, Any]]:
    """Return the small, explicitly curated public reference catalog."""
    return [deepcopy(case) for case in _PUBLIC_CASES.values()]


def get_public_case(case_id: str) -> dict[str, Any] | None:
    case = _PUBLIC_CASES.get(case_id)
    return deepcopy(case) if case is not None else None


def classify_comparison(real_state: str, cryptotrace_state: str, *, external_action: bool = False) -> str:
    """Classify comparable observations without treating actions as matches."""
    if external_action:
        return "NOT_COMPARABLE"
    if real_state == "documented" and cryptotrace_state == "detected":
        return "MATCH"
    if real_state in {"documented", "partially_documented"} and cryptotrace_state in {"detected", "partially_observable"}:
        return "PARTIAL_MATCH"
    if cryptotrace_state == "not_observable":
        return "NOT_OBSERVABLE"
    return "NOT_COMPARABLE"


def build_comparison(case_id: str) -> dict[str, Any] | None:
    """Build the honest comparison for the curated reference record."""
    case = get_public_case(case_id)
    if case is None:
        return None

    source = {
        "authority": case["source_authority"],
        "type": case["source_type"],
        "url": case["source_url"],
    }
    if case_id == ANALYZABLE_PUBLIC_CASE_ID:
        crypto_message = (
            "NOT OBSERVABLE WITH CURRENT PROVIDER: the public case publishes a Bitcoin "
            "address, amount, and seizure date, but CryptoTrace currently has no live "
            "Bitcoin data provider. No synthetic investigation was run."
        )
        rows = [
            {
                "element": "Public wallet identifier",
                "real_case": f"Bitcoin address explicitly disclosed: {ANALYZABLE_WALLET}.",
                "cryptotrace": crypto_message,
                "result": classify_comparison("documented", "not_observable"),
                "why": "The public identifier is available, but the current provider cannot retrieve or trace this real Bitcoin address.",
                "evidence": [ANALYZABLE_WALLET],
                "source": "Official press release, paragraph 2",
            },
            {
                "element": "Fund movement",
                "real_case": "The release documents 20.2891382 BTC seized from the identified address on April 15, 2025.",
                "cryptotrace": crypto_message,
                "result": classify_comparison("documented", "not_observable"),
                "why": "A defensible CryptoTrace movement comparison requires a connected Bitcoin data source; the current provider is DemoProvider-only.",
                "evidence": [ANALYZABLE_WALLET],
                "source": "Official press release, paragraph 2",
            },
            {
                "element": "Address context",
                "real_case": "The source says the address was allegedly associated with a member of the Chaos ransomware group.",
                "cryptotrace": crypto_message,
                "result": classify_comparison("documented", "not_observable"),
                "why": "CryptoTrace does not convert the source's allegation into an independent attribution or finding.",
                "evidence": [ANALYZABLE_WALLET],
                "source": "Official press release, paragraph 3",
            },
            {
                "element": "Transaction hash",
                "real_case": "NOT PUBLICLY DISCLOSED in the official press release.",
                "cryptotrace": "No transaction was analyzed.",
                "result": classify_comparison("documented", "not_observable"),
                "why": "The source provides an address, amount, and date but no transaction hash for a direct hash-level comparison.",
                "evidence": [],
                "source": "Official press release, paragraph 2",
            },
            {
                "element": "External asset action",
                "real_case": "Dallas FBI executed the cryptocurrency seizure described in the release.",
                "cryptotrace": "CryptoTrace can record Freeze Readiness or prepare an operational request; it does not execute or verify an external seizure.",
                "result": classify_comparison("documented", "prepared", external_action=True),
                "why": "An external law-enforcement seizure and an internal CryptoTrace request are different operational events.",
                "evidence": [],
                "source": "Official press release, paragraphs 1 and 3",
            },
        ]
        counts = {state: sum(1 for row in rows if row["result"] == state) for state in ("MATCH", "PARTIAL_MATCH", "NOT_OBSERVABLE", "NOT_COMPARABLE")}
        return {
            "case": case,
            "source": source,
            "cryptotrace": {
                "status": "NOT_OBSERVABLE",
                "message": crypto_message,
                "is_demo": False,
                "wallets": [],
                "transaction_references": [],
                "findings": [],
                "recommendations": [],
                "attribution": None,
            },
            "rows": rows,
            "alignment": {
                "label": "COMPARABLE ELEMENTS ONLY",
                "comparable_elements": len(rows) - counts["NOT_COMPARABLE"],
                "matched": counts["MATCH"],
                "partial": counts["PARTIAL_MATCH"],
                "not_observable": counts["NOT_OBSERVABLE"],
                "not_comparable": counts["NOT_COMPARABLE"],
            },
            "limitations": (
                "This comparison evaluates overlap between publicly documented case facts and "
                "CryptoTrace's available analytical outputs. It does not establish that "
                "CryptoTrace independently reproduced the full original investigation or legal outcome."
            ),
        }
    crypto_message = (
        "NOT OBSERVABLE WITH CURRENT DATA: the public case record does not publish "
        "an exact wallet address or transaction reference that CryptoTrace can analyze. "
        "No synthetic investigation was run."
    )
    rows = [
        {
            "element": "Fund movement",
            "real_case": "Documented movement through six accounts before cryptocurrency purchase.",
            "cryptotrace": crypto_message,
            "result": classify_comparison("documented", "not_observable"),
            "why": "The source documents movement, but does not provide analyzable on-chain identifiers.",
            "evidence": [],
            "source": "Official document, pages 1–2",
        },
        {
            "element": "Destination",
            "real_case": "Cryptocurrency purchase in Dubai is documented; an analyzable destination wallet is not published.",
            "cryptotrace": crypto_message,
            "result": classify_comparison("partially_documented", "not_observable"),
            "why": "The source does not disclose a destination address for independent graph analysis.",
            "evidence": [],
            "source": "Official document, pages 1–2",
        },
        {
            "element": "Pattern",
            "real_case": "Layering across bank accounts is described in the source.",
            "cryptotrace": crypto_message,
            "result": classify_comparison("documented", "not_observable"),
            "why": "CryptoTrace cannot claim a blockchain pattern without the source wallet and transactions.",
            "evidence": [],
            "source": "Official document, page 2",
        },
        {
            "element": "Asset / network",
            "real_case": "USDT conversion and a Tron wallet are mentioned; exact wallet and transaction references are not published.",
            "cryptotrace": crypto_message,
            "result": classify_comparison("partially_documented", "not_observable"),
            "why": "The asset/network description alone is insufficient to run the existing trace engine.",
            "evidence": [],
            "source": "Official document, page 2",
        },
        {
            "element": "External asset action",
            "real_case": "The source reports funds frozen in bank accounts.",
            "cryptotrace": "CryptoTrace can record Freeze Readiness or prepare an operational request; it does not execute or verify an external freeze.",
            "result": classify_comparison("documented", "prepared", external_action=True),
            "why": "An external outcome and an internal request workflow are different operational events.",
            "evidence": [],
            "source": "Official document, page 3",
        },
    ]
    counts = {state: sum(1 for row in rows if row["result"] == state) for state in ("MATCH", "PARTIAL_MATCH", "NOT_OBSERVABLE", "NOT_COMPARABLE")}
    return {
        "case": case,
        "source": source,
        "cryptotrace": {
            "status": "NOT_OBSERVABLE",
            "message": crypto_message,
            "is_demo": False,
            "wallets": [],
            "transaction_references": [],
            "findings": [],
            "recommendations": [],
            "attribution": None,
        },
        "rows": rows,
        "alignment": {
            "label": "COMPARABLE ELEMENTS ONLY",
            "comparable_elements": 4,
            "matched": counts["MATCH"],
            "partial": counts["PARTIAL_MATCH"],
            "not_observable": counts["NOT_OBSERVABLE"],
            "not_comparable": counts["NOT_COMPARABLE"],
        },
        "limitations": (
            "This comparison evaluates overlap between publicly documented case facts and "
            "CryptoTrace's available analytical outputs. It does not establish that "
            "CryptoTrace independently reproduced the full original investigation or legal outcome."
        ),
    }
