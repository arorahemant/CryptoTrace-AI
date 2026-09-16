"""One deterministic destination policy; a frontier is not a proven endpoint."""
from sqlalchemy import select
from app.models.models import Wallet, VASPAttribution
from app.services.attribution_service import normalize_attribution, resolve_attributions


def classify_candidates(wallets: dict, attributions: dict) -> list[dict]:
    candidates = []
    for address, wallet in wallets.items():
        if wallet.get("is_reported"):
            continue
        attribution = attributions.get(address, {})
        status = attribution.get("attribution_status", "unknown")
        kind = wallet.get("endpoint_kind", "not_expanded")
        if status == 'unknown' and kind in {'candidate_vasp', 'identified_service_address'}:
            kind = 'last_observed_wallet' if wallet.get('expansion_state') == 'expanded' else 'not_expanded'
        if status == "known_verified":
            kind = "identified_service_address"
        elif status == "likely_inferred":
            kind = "candidate_vasp"
        if kind not in {"identified_service_address", "candidate_vasp", "last_observed_wallet", "not_expanded"}:
            continue
        candidates.append({"address": address, "kind": kind,
                           "expansion_state": wallet.get("expansion_state", "legacy_unknown"),
                           "hop_distance": wallet.get("hop_distance") or 0,
                           "attribution_status": status})
    rank = {"identified_service_address": 0, "candidate_vasp": 1,
            "last_observed_wallet": 2, "not_expanded": 3}
    # Prefer supported services, then nearest observed endpoint, then frontier.
    # Ties use address, never incomparable asset values or database row order.
    return sorted(candidates, key=lambda c: (rank[c["kind"]], c["hop_distance"], c["address"]))


async def destination_context(db, case) -> dict:
    from app.core.capabilities import current_observation
    if not current_observation(case):
        return {"selected": None, "candidates": [], "policy": "no_current_observation", "attribution": normalize_attribution({}), "attributions": {}}
    attributions = await resolve_attributions(db, case)
    if getattr(case.blockchain, "value", None) == "ethereum":
        stats = (case.analysis_summary or {}).get("stats", {})
        def current_candidate(candidate):
            if not candidate:
                return None
            status = attributions.get(candidate['address'], {}).get('attribution_status', 'unknown')
            kind = candidate['kind']
            if status == 'known_verified':
                kind = 'identified_service_address'
            elif status == 'likely_inferred':
                kind = 'candidate_vasp'
            return {**candidate, 'attribution_status': status, 'kind': kind}
        selected = current_candidate(stats.get("destination"))
        return {"selected": selected, "candidates": [current_candidate(c) for c in stats.get("destination_candidates", [])],
                "policy": "current_run_selection", "attributions": attributions,
                "attribution": attributions.get(selected['address'], normalize_attribution({})) if selected else normalize_attribution({})}
    wallets = (await db.scalars(select(Wallet).where(Wallet.case_id == case.id))).all()
    wallet_data = {w.address: {"is_reported": w.is_reported, "hop_distance": w.hop_distance,
                               **(w.metadata_ or {})} for w in wallets}
    candidates = classify_candidates(wallet_data, attributions)
    return {"selected": candidates[0] if candidates else None, "candidates": candidates,
            "policy": "supported-service_then_observed-endpoint_then_frontier; nearest-hop_then_address",
            "attributions": attributions, "attribution": attributions.get(candidates[0]['address'], normalize_attribution({})) if candidates else normalize_attribution({})}


async def destination_intelligence(db, case, graph):
    from app.core.capabilities import capability_payload
    from app.models.models import Evidence, PatternFinding
    selection = await destination_context(db, case)
    capability = capability_payload(case)
    selected = selection['selected']
    address = selected['address'] if selected else None
    path = graph.get('primary_path', []) if selected else []
    pairs = set(zip(path, path[1:]))
    transfers = [t for t in graph.get('edges', []) if (t['source'], t['target']) in pairs or t['target'] == address]
    ids = {t['id'] for t in transfers}
    hashes = {t['hash'] for t in transfers}
    rows = (await db.scalars(select(Evidence).where(Evidence.case_id == case.id))).all()
    evidence = [e for e in rows if (case.blockchain.value == 'demo' or (e.metadata_ or {}).get('run_id') == capability['run_id']) and
        (e.wallet_address == address or ((e.metadata_ or {}).get('transfer_id') in ids) or
         (not (e.metadata_ or {}).get('transfer_id') and e.transaction_hash in hashes))]
    findings = (await db.scalars(select(PatternFinding).where(PatternFinding.case_id == case.id))).all()
    attribution = selection['attribution']
    verified_at = attribution.get('verified_at')
    basis = {
        'identified_service_address': 'Supported service candidate, ranked by nearest observed hop and then address.',
        'candidate_vasp': 'Inferred service candidate, ranked by nearest observed hop and then address. Investigator verification is required.',
        'last_observed_wallet': 'Nearest observed endpoint in the bounded trace; address breaks equal-hop ties. Service identity is unknown.',
        'not_expanded': 'Unexpanded trace frontier, ranked by nearest hop and then address. Further observation is incomplete.',
    }.get(selected['kind'] if selected else '', 'NOT AVAILABLE: no current destination candidate.')
    return {'run_id': capability['run_id'], 'network': case.blockchain.value,
        'data_origin': capability['data_origin'], 'coverage': capability.get('coverage'),
        'candidate': selected, 'attribution': attribution,
        'selection_basis': basis, 'selection_policy': selection['policy'], 'supporting_path': path,
        'supporting_transfers': transfers,
        'evidence': [{'id': str(e.id), 'title': e.title, 'finding_id': str(e.finding_id) if e.finding_id else None,
            'transfer_id': (e.metadata_ or {}).get('transfer_id'), 'transaction_hash': e.transaction_hash, 'source': e.source} for e in evidence],
        'findings': [{'id': str(f.id), 'title': f.pattern_name,
            'transfer_ids': [t['id'] for t in transfers if t['id'] in (f.metadata_ or {}).get('supporting_transfer_ids', []) or
                (not (f.metadata_ or {}).get('supporting_transfer_ids') and t['hash'] in (f.supporting_transaction_ids or []))],
            'evidence_ids': [str(e.id) for e in evidence if e.finding_id == f.id]} for f in findings if
            address in (f.affected_wallets or []) or hashes.intersection(f.supporting_transaction_ids or [])],
        'observation_provider': capability['provider'], 'external_attribution_provider': 'not_connected',
        'verified_at': verified_at.isoformat() if hasattr(verified_at, 'isoformat') else verified_at,
        'freshness': 'verification_recorded_not_revalidated' if verified_at else 'unknown',
        'retrieved_at': (capability.get('coverage') or {}).get('retrieved_at') or capability.get('processed_at'),
        'limitations': ['Observed relationships do not prove ownership, custody, fraud, fund continuity or recoverability.',
            'No external attribution provider is connected. Verification freshness is not independently checked.',
            'Supporting transfers establish observed connections; they do not independently verify an entity.'] + capability['limitations']}
