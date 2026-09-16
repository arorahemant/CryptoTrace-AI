"""Deterministic case/run explanations. No model, network or provider calls."""
QUESTIONS = [
    'Explain the observed money trail.', 'Why is this the leading destination?',
    'What evidence supports this candidate?', 'Which transfers support this finding?',
    'Why was this wallet flagged?', 'What should I review next?',
    'What information is still missing?', 'Why is attribution UNKNOWN?',
]
LABELS = {'known_verified': 'VERIFIED', 'likely_inferred': 'LIKELY / INFERRED', 'unknown': 'UNKNOWN'}


def explain(question, context):
    q = question.lower()
    intelligence = context.get('destination_intelligence') or {}
    attribution = intelligence.get('attribution') or {}
    candidate = intelligence.get('candidate') or context.get('destination')
    status = LABELS.get(attribution.get('attribution_status'), 'UNKNOWN')
    transactions = context.get('key_transactions', [])
    evidence = context.get('evidence', [])
    findings = context.get('findings', [])
    wallet = context.get('selected_wallet')
    finding = context.get('selected_finding')
    sections, records = [], []

    def section(title, *items):
        sections.append({'title': title, 'items': list(items)})

    def transfer_records(items):
        for t in items:
            identity = t.get('transfer_id') or t.get('id')
            if not identity:
                continue
            amount = t.get('amount_exact')
            label = f"{amount} {t.get('asset', '')}" if amount is not None else 'Exact amount NOT AVAILABLE'
            records.append({'kind': 'transfer', 'id': identity, 'label': label, 'transaction_hash': t['hash'],
                'source': t.get('source') or intelligence.get('observation_provider') or 'persisted_transfer'})

    def evidence_records(items):
        records.extend({'kind': 'evidence', 'id': e['id'], 'label': e['title'], 'source': e.get('source') or 'saved_evidence'} for e in items if e.get('id'))

    def finding_records(items):
        records.extend({'kind': 'finding', 'id': f['id'], 'label': f['pattern'], 'source': 'recorded_finding'} for f in items)

    if wallet and wallet not in {w['address'] for w in context.get('wallets', [])} or finding and finding not in {f['id'] for f in findings}:
        section('NOT AVAILABLE', 'The selected object is unavailable in this case/run.')
    elif any(word in q for word in ('destination', 'candidate', 'vasp', 'exchange', 'attribution', 'attribute', 'entity')):
        section('Destination intelligence', f"Candidate: {candidate['address'] if candidate else 'UNKNOWN'}", f'Attribution: {status}',
            'Entity: ' + (attribution.get('entity_name') or 'UNKNOWN'),
            'Selection basis: ' + intelligence.get('selection_basis', 'NOT AVAILABLE'),
            'Attribution basis: ' + (attribution.get('reasoning') or 'No sufficiently supported attribution record is available.'))
        if candidate:
            records.append({'kind': 'wallet', 'id': candidate['address'], 'label': 'Destination candidate', 'source': 'shared_destination_selection'})
        supported_ids = {t['id'] for t in intelligence.get('supporting_transfers', [])}
        transfer_records([t for t in transactions if t.get('transfer_id') in supported_ids])
        evidence_records(intelligence.get('evidence', []))
    elif any(word in q for word in ('missing', 'unavailable', 'unknown')):
        section('Missing information', f'Attribution: {status}', 'External attribution provider: NOT CONNECTED',
            'Ownership, current custody, recoverability and external action: UNKNOWN',
            'Coverage: ' + (context.get('coverage') or {}).get('state', 'demo' if context.get('case', {}).get('is_demo') else 'NOT AVAILABLE'))
    elif 'next' in q:
        recommendations = context.get('recommendations', [])
        section('Next review step', recommendations[0]['action'] if recommendations else 'Review current coverage and saved evidence; no next action is recorded.')
        if recommendations:
            ids = {str(e) for e in recommendations[0].get('evidence_ids', [])}
            evidence_records([e for e in evidence if e.get('id') in ids])
    elif 'this finding' in q and not finding:
        section('Finding selection', 'Select a recorded finding to inspect its supporting transfers.' if findings else 'NOT AVAILABLE: no finding is recorded for this observation.')
        finding_records(findings)
    elif any(word in q for word in ('finding', 'flag', 'suspicious', 'pattern')):
        selected = [f for f in findings if (not finding or f['id'] == finding) and (not wallet or wallet in f.get('affected_wallets', []))]
        section('Recorded findings', f'{len(selected)} recorded finding(s) match this selection.' if selected else 'NOT AVAILABLE: no recorded finding supports a flag for this selection. Activity volume alone does not establish wrongdoing.')
        finding_records(selected)
        ids = {i for f in selected for i in f.get('supporting_transfer_ids', [])}
        hashes = {h for f in selected if not f.get('supporting_transfer_ids') for h in f.get('supporting_transactions', [])}
        transfer_records([t for t in transactions if t.get('transfer_id') in ids or t['hash'] in hashes])
        evidence_records([e for e in evidence if e.get('finding_id') in {f['id'] for f in selected}])
    elif any(word in q for word in ('evidence', 'support', 'transaction', 'transfer')):
        selected = [t for t in transactions if not wallet or wallet in (t.get('from'), t.get('to'))]
        section('Supporting records', f'{len(selected)} recorded transfer events in the selected scope. References below link to existing objects.')
        transfer_records(selected)
        ids = {t.get('transfer_id') for t in selected}
        hashes = {t['hash'] for t in selected}
        evidence_records([e for e in evidence if e.get('transfer_id') in ids or (not e.get('transfer_id') and e.get('transaction_hash') in hashes)])
    elif any(word in q for word in ('trail', 'money', 'flow', 'path', 'where')):
        section('Observed money trail', f"{context.get('transactions_count', 0)} transfer events across {len(context.get('wallets', []))} addresses.",
            'Supporting path: ' + (' → '.join(intelligence.get('supporting_path', [])) or 'NOT AVAILABLE'),
            'The path shows observed connections; fund continuity is not established.')
        ids = {t['id'] for t in intelligence.get('supporting_transfers', [])}
        transfer_records([t for t in transactions if t.get('transfer_id') in ids])
    elif 'intermediar' in q:
        intermediaries = [w for w in context.get('wallets', []) if w.get('is_intermediary') and (not wallet or w['address'] == wallet)]
        section('Recorded intermediary roles', f'{len(intermediaries)} address(es) have a recorded intermediary role. A structural role does not establish common ownership or fund continuity.')
        records.extend({'kind': 'wallet', 'id': w['address'], 'label': w.get('label') or w['address'], 'source': 'recorded_graph_role'} for w in intermediaries)
    elif any(word in q for word in ('risk', 'score')):
        addresses = {w['address'] for w in context.get('wallets', [])}
        risks = [r for r in context.get('risk_assessments', []) if r['wallet'] in addresses and (not wallet or r['wallet'] == wallet)]
        section('Recorded risk assessments', *([f"{r['wallet']}: {r['category']} ({r['score']}/100), as recorded; not a fraud confirmation." for r in risks] or ['NOT AVAILABLE: no risk assessment is recorded for this selection.']))
        records.extend({'kind': 'wallet', 'id': r['wallet'], 'label': 'Recorded risk assessment', 'source': 'persisted_risk_assessment'} for r in risks)
    else:
        section('Investigation Summary', f"{context.get('transactions_count', 0)} transfer events; {len(context.get('wallets', []))} addresses; {len(findings)} recorded findings.",
            f"Destination: {candidate['address'] if candidate else 'UNKNOWN'}; attribution: {status}.")
        finding_records(findings)
    unique = {(r['kind'], r['id']): r for r in records}
    recommendations = context.get('recommendations', [])
    next_step = recommendations[0]['action'] if recommendations else 'NOT AVAILABLE — review current coverage and saved evidence.'
    return {'answer': '\n'.join(s['title'] + ': ' + ' '.join(s['items']) for s in sections), 'next_review_step': next_step,
        'grounded': True, 'sections': sections, 'supporting_records': list(unique.values()),
        'sources': ['persisted_case_run', 'shared_destination_attribution'], 'suggested_questions': QUESTIONS}
