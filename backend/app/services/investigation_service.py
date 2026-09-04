"""
CryptoTrace AI - Investigation Service
Orchestrates the full investigation pipeline:
Trace → Graph → Fund Flow → Patterns → Risk → Evidence → Timeline
"""
import logging
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import (
    Case, Wallet, Transaction, FundFlow, PatternFinding,
    VASPAttribution, RiskAssessment, Evidence, InvestigationEvent,
    CaseStatus, Blockchain, PatternType, Severity, RiskCategory,
    AttributionConfidence,
)
from app.providers import get_provider
from app.providers.base import BlockchainProvider
from app.providers.demo import DemoProvider
from app.engines.trace_engine import TraceEngine
from app.engines.graph_engine import GraphEngine
from app.engines.pattern_engine import PatternEngine
from app.engines.risk_engine import RiskEngine
from app.services.attribution_service import normalize_attribution

logger = logging.getLogger(__name__)
_investigation_locks: dict[str, asyncio.Lock] = {}


def _get_investigation_lock(case_id: str) -> asyncio.Lock:
    """Return the process-local lock used to serialize one case's run."""
    # The lookup/creation has no await point, so concurrent coroutines in the
    # same event loop cannot create two locks for the same case.
    return _investigation_locks.setdefault(case_id, asyncio.Lock())


class InvestigationService:
    """
    Orchestrates the complete investigation pipeline.
    This is the primary service that connects all engines.
    """

    def __init__(self, db: AsyncSession, provider: Optional[BlockchainProvider] = None):
        self.db = db
        self.provider = provider or get_provider("demo")
        self.trace_engine = TraceEngine(self.provider)
        self.graph_engine = GraphEngine()
        self.pattern_engine = PatternEngine()
        self.risk_engine = RiskEngine()

    async def run_investigation(
        self,
        case_id: str,
        max_hops: int = 5,
        min_amount: float = 0.001,
        time_window_hours: int = 720,
        direction: str = "outgoing",
    ) -> Dict[str, Any]:
        """Run one case investigation at a time and reuse persisted results."""
        async with _get_investigation_lock(str(case_id)):
            return await self._run_investigation(
                case_id=case_id,
                max_hops=max_hops,
                min_amount=min_amount,
                time_window_hours=time_window_hours,
                direction=direction,
            )

    async def _run_investigation(
        self,
        case_id: str,
        max_hops: int = 5,
        min_amount: float = 0.001,
        time_window_hours: int = 720,
        direction: str = "outgoing",
    ) -> Dict[str, Any]:
        """
        Run the complete investigation pipeline for a case.

        Pipeline:
        1. Fetch case and validate
        2. Trace from reported wallet
        3. Build graph
        4. Detect fund flow paths
        5. Detect patterns
        6. VASP attribution
        7. Risk assessment
        8. Generate evidence
        9. Build timeline

        Returns a comprehensive investigation result.
        """
        # 1. Fetch and lock the case. PostgreSQL holds this row lock through
        # the request transaction; the process-local lock above covers the
        # SQLite/demo path where FOR UPDATE is a no-op.
        case = await self.db.scalar(
            select(Case)
            .where(Case.id == uuid.UUID(case_id))
            .with_for_update()
        )
        if not case:
            raise ValueError(f"Case {case_id} not found")

        # A case has one current investigation snapshot. Repeated clicks or
        # retries after a successful request return that snapshot instead of
        # appending another set of child rows. A failed request is rolled back
        # by the request transaction, so it remains retryable.
        if await self._has_persisted_investigation(case):
            logger.info("Reusing persisted investigation for case %s", case.case_number)
            return await self._load_persisted_result(case)

        # Update case status
        case.status = CaseStatus.INVESTIGATING
        await self.db.flush()

        reported_wallet = case.reported_wallet
        chain = case.blockchain.value if case.blockchain else "demo"

        logger.info(f"Starting investigation for case {case.case_number}, wallet: {reported_wallet}")

        # 2. Trace
        trace_result = await self.trace_engine.trace(
            starting_address=reported_wallet,
            chain=chain,
            max_hops=max_hops,
            min_amount=min_amount,
            time_window_hours=time_window_hours,
            direction=direction,
        )

        raw_transactions = trace_result["transactions"]
        raw_wallets = trace_result["wallets"]
        paths = trace_result["paths"]
        stats = trace_result["stats"]
        # Stable API aliases used by the investigator UI and validation suite.
        # Keep the canonical trace keys above for provider-level consumers.
        stats["traced_transactions"] = stats.get("total_transactions", 0)
        stats["discovered_wallets"] = stats.get("total_wallets", 0)
        stats["hops_completed"] = stats.get("max_hop_reached", 0)

        # Supplement wallet metadata from demo provider
        if isinstance(self.provider, DemoProvider):
            demo_wallets = self.provider.get_demo_wallets()
            for addr, meta in demo_wallets.items():
                if addr in raw_wallets:
                    raw_wallets[addr].update({
                        "label": meta.get("label", raw_wallets[addr].get("label")),
                        "is_suspicious": meta.get("is_suspicious", raw_wallets[addr].get("is_suspicious", False)),
                        "is_intermediary": meta.get("is_intermediary", raw_wallets[addr].get("is_intermediary", False)),
                        "is_destination": meta.get("is_destination", raw_wallets[addr].get("is_destination", False)),
                        "is_reported": meta.get("is_reported", raw_wallets[addr].get("is_reported", False)),
                    })

        # 3. Save wallets to DB
        await self._save_wallets(case, raw_wallets, chain)

        # 4. Save transactions to DB
        await self._save_transactions(case, raw_transactions, chain)

        # 5. Build graph
        graph = self.graph_engine.build_graph(raw_transactions, raw_wallets)
        primary_path = self.graph_engine.get_primary_path(reported_wallet)
        intermediaries = self.graph_engine.get_intermediaries()

        # 6. Detect patterns
        findings = self.pattern_engine.detect_all(raw_transactions, raw_wallets, paths)
        stats["findings"] = len(findings)
        finding_records = await self._save_findings(case, findings)

        # 7. VASP attribution
        vasp_data = await self._get_vasp_attributions(case, raw_wallets, raw_transactions)

        # 8. Risk assessment
        risk_results = self.risk_engine.assess_case_risk(
            wallets=raw_wallets,
            findings=findings,
            vasp_data=vasp_data,
            intermediary_data=intermediaries,
        )
        await self._save_risk_assessments(case, risk_results)

        # 9. Generate evidence
        await self._generate_evidence(
            case,
            findings,
            finding_records,
            risk_results,
            vasp_data,
            raw_transactions,
        )

        # 10. Build timeline
        await self._build_timeline(case, raw_transactions, findings)

        # 11. Save fund flows
        await self._save_fund_flows(case, raw_transactions, primary_path)

        # Serialize graph for frontend
        graph_data = self.graph_engine.serialize_for_frontend(
            primary_path=primary_path,
            vasp_data=vasp_data,
            risk_data=risk_results,
        )

        case.status = (
            CaseStatus.REVIEW
            if stats.get("trace_status") == "partial"
            else CaseStatus.COMPLETED
        )
        await self.db.flush()

        overall_risk = self.risk_engine.get_overall_risk(risk_results)

        return {
            "case_id": str(case.id),
            "case_number": case.case_number,
            "status": case.status.value,
            "is_demo": stats.get("is_demo", True),
            "stats": stats,
            "graph": graph_data,
            "primary_path": primary_path,
            "intermediaries": intermediaries,
            "findings": findings,
            "risk": {
                "overall": overall_risk,
                "by_wallet": {
                    addr: {
                        "risk_score": r["risk_score"],
                        "risk_category": r["risk_category"],
                        "signals_count": len(r["contributing_signals"]),
                    }
                    for addr, r in risk_results.items()
                },
            },
            "vasp_attributions": vasp_data,
            "fund_flow_summary": {
                "total_amount_origin": sum(
                    tx["amount"] for tx in raw_transactions
                    if tx["from_address"] == reported_wallet
                ),
                "max_hops": stats.get("max_hop_reached", 0),
                "paths_count": len(paths),
            },
        }

    async def _has_persisted_investigation(self, case: Case) -> bool:
        """Return whether this case already has an investigation snapshot."""
        if case.status in (CaseStatus.COMPLETED, CaseStatus.REVIEW):
            return True

        # Older demo databases predate the completed/review status update.
        # Their wallet rows still identify a previously materialized run.
        wallet_id = await self.db.scalar(
            select(Wallet.id).where(Wallet.case_id == case.id).limit(1)
        )
        return wallet_id is not None

    async def _load_persisted_result(self, case: Case) -> Dict[str, Any]:
        """Reconstruct the public result from the case's stored snapshot."""
        wallet_rows = (
            await self.db.execute(
                select(Wallet)
                .where(Wallet.case_id == case.id)
                .order_by(Wallet.created_at, Wallet.address)
            )
        ).scalars().all()
        transaction_rows = (
            await self.db.execute(
                select(Transaction)
                .where(Transaction.case_id == case.id)
                .order_by(Transaction.timestamp, Transaction.hash)
            )
        ).scalars().all()
        finding_rows = (
            await self.db.execute(
                select(PatternFinding)
                .where(PatternFinding.case_id == case.id)
                .order_by(PatternFinding.created_at, PatternFinding.id)
            )
        ).scalars().all()
        risk_rows = (
            await self.db.execute(
                select(RiskAssessment)
                .where(RiskAssessment.case_id == case.id)
                .order_by(RiskAssessment.wallet_address)
            )
        ).scalars().all()
        vasp_rows = (
            await self.db.execute(
                select(VASPAttribution)
                .where(VASPAttribution.case_id == case.id)
                .order_by(VASPAttribution.wallet_address)
            )
        ).scalars().all()

        raw_wallets = {
            wallet.address: {
                "address": wallet.address,
                "label": wallet.label,
                "is_reported": wallet.is_reported,
                "is_intermediary": wallet.is_intermediary,
                "is_destination": wallet.is_destination,
                "is_suspicious": wallet.is_suspicious,
                "hop_distance": wallet.hop_distance,
                "total_received": wallet.total_received or 0.0,
                "total_sent": wallet.total_sent or 0.0,
                "transaction_count": wallet.transaction_count or 0,
            }
            for wallet in wallet_rows
        }
        if not raw_wallets:
            raw_wallets[case.reported_wallet] = {
                "address": case.reported_wallet,
                "is_reported": True,
                "is_intermediary": False,
                "is_destination": False,
                "is_suspicious": True,
                "hop_distance": 0,
                "total_received": 0.0,
                "total_sent": 0.0,
                "transaction_count": 0,
            }

        raw_transactions = [
            {
                "hash": transaction.hash,
                "from_address": transaction.from_address,
                "to_address": transaction.to_address,
                "amount": transaction.amount,
                "asset": transaction.asset,
                "timestamp": transaction.timestamp,
                "is_suspicious": transaction.is_suspicious,
                "hop_number": transaction.hop_number,
            }
            for transaction in transaction_rows
        ]

        self.graph_engine.build_graph(raw_transactions, raw_wallets)
        primary_path = self.graph_engine.get_primary_path(case.reported_wallet)
        intermediaries = self.graph_engine.get_intermediaries()

        vasp_data = {
            record.wallet_address: normalize_attribution(record)
            for record in vasp_rows
        }
        risk_results = {
            record.wallet_address: {
                "wallet_address": record.wallet_address,
                "risk_score": record.risk_score,
                "risk_category": record.risk_category.value if record.risk_category else "low",
                "contributing_signals": record.contributing_signals or [],
                "explanation": record.explanation or "",
            }
            for record in risk_rows
        }
        findings = [
            {
                "pattern_type": record.pattern_type.value if record.pattern_type else "",
                "pattern_name": record.pattern_name,
                "description": record.description,
                "severity": record.severity.value if record.severity else "medium",
                "confidence": record.confidence,
                "trigger": record.trigger,
                "affected_wallets": record.affected_wallets or [],
                "supporting_transaction_ids": record.supporting_transaction_ids or [],
                "metadata": record.metadata_ or {},
            }
            for record in finding_rows
        ]

        max_hop = max((tx.get("hop_number", 0) or 0 for tx in raw_transactions), default=0)
        trace_status = "partial" if case.status == CaseStatus.REVIEW else "complete"
        stats = {
            "total_transactions": len(raw_transactions),
            "total_wallets": len(raw_wallets),
            "max_hop_reached": max_hop,
            "total_amount_traced": sum(tx.get("amount", 0) for tx in raw_transactions),
            "provider": self.provider.provider_name,
            "is_demo": case.is_demo,
            "provider_errors": 0,
            "malformed_transactions": 0,
            "trace_status": trace_status,
            "trace_warning": (
                "Trace incomplete: one or more provider responses were unavailable "
                "or malformed; results may be incomplete."
                if trace_status == "partial"
                else None
            ),
            "traced_transactions": len(raw_transactions),
            "discovered_wallets": len(raw_wallets),
            "hops_completed": max_hop,
            "findings": len(findings),
        }
        graph_data = self.graph_engine.serialize_for_frontend(
            primary_path=primary_path,
            vasp_data=vasp_data,
            risk_data=risk_results,
        )
        overall_risk = self.risk_engine.get_overall_risk(risk_results)

        return {
            "case_id": str(case.id),
            "case_number": case.case_number,
            "status": case.status.value,
            "is_demo": case.is_demo,
            "stats": stats,
            "graph": graph_data,
            "primary_path": primary_path,
            "intermediaries": intermediaries,
            "findings": findings,
            "risk": {
                "overall": overall_risk,
                "by_wallet": {
                    address: {
                        "risk_score": risk["risk_score"],
                        "risk_category": risk["risk_category"],
                        "signals_count": len(risk["contributing_signals"]),
                    }
                    for address, risk in risk_results.items()
                },
            },
            "vasp_attributions": vasp_data,
            "fund_flow_summary": {
                "total_amount_origin": sum(
                    tx["amount"]
                    for tx in raw_transactions
                    if tx["from_address"] == case.reported_wallet
                ),
                "max_hops": max_hop,
                "paths_count": 1 if primary_path else 0,
            },
        }

    async def _save_wallets(self, case: Case, wallets: Dict, chain: str):
        """Persist discovered wallets."""
        blockchain_enum = Blockchain(chain) if chain in [e.value for e in Blockchain] else Blockchain.DEMO
        for address, meta in wallets.items():
            wallet = Wallet(
                case_id=case.id,
                address=address,
                blockchain=blockchain_enum,
                label=meta.get("label"),
                is_reported=meta.get("is_reported", False),
                is_intermediary=meta.get("is_intermediary", False),
                is_destination=meta.get("is_destination", False),
                is_suspicious=meta.get("is_suspicious", False),
                hop_distance=meta.get("hop_distance"),
                total_received=meta.get("total_received", 0),
                total_sent=meta.get("total_sent", 0),
                transaction_count=meta.get("transaction_count", 0),
            )
            self.db.add(wallet)

    async def _save_transactions(self, case: Case, transactions: List[Dict], chain: str):
        """Persist traced transactions in canonical format."""
        blockchain_enum = Blockchain(chain) if chain in [e.value for e in Blockchain] else Blockchain.DEMO
        for tx in transactions:
            transaction = Transaction(
                case_id=case.id,
                hash=tx["hash"],
                blockchain=blockchain_enum,
                block_number=tx.get("block_number"),
                timestamp=tx["timestamp"],
                from_address=tx["from_address"],
                to_address=tx["to_address"],
                asset=tx.get("asset", "ETH"),
                amount=tx["amount"],
                amount_usd=tx.get("amount_usd"),
                fee=tx.get("fee"),
                status=tx.get("status", "confirmed"),
                source=tx.get("source", "demo"),
                is_suspicious=tx.get("is_suspicious", False),
                hop_number=tx.get("hop_number"),
            )
            self.db.add(transaction)

    async def _save_findings(self, case: Case, findings: List[Dict]) -> List[PatternFinding]:
        """Persist pattern findings and return records for evidence linkage."""
        records = []
        for f in findings:
            pt = f.get("pattern_type", "rapid_movement")
            pattern_type = PatternType(pt) if pt in [e.value for e in PatternType] else PatternType.RAPID_MOVEMENT
            sev = f.get("severity", "medium")
            severity = Severity(sev) if sev in [e.value for e in Severity] else Severity.MEDIUM

            finding = PatternFinding(
                case_id=case.id,
                pattern_type=pattern_type,
                pattern_name=f["pattern_name"],
                description=f["description"],
                severity=severity,
                confidence=f.get("confidence", 0.5),
                trigger=f.get("trigger"),
                affected_wallets=f.get("affected_wallets", []),
                supporting_transaction_ids=f.get("supporting_transaction_ids", []),
                metadata_=f.get("metadata"),
            )
            self.db.add(finding)
            records.append(finding)
        await self.db.flush()
        return records

    async def _get_vasp_attributions(self, case: Case, wallets: Dict, transactions: List[Dict]) -> Dict[str, Dict]:
        """Get VASP attributions for discovered wallets."""
        vasp_data = {}
        if isinstance(self.provider, DemoProvider):
            for address in wallets:
                vasp = self.provider.get_demo_vasp(address)
                if vasp:
                    normalized = normalize_attribution(vasp)
                    normalized["supporting_transaction_hashes"] = [
                        tx["hash"] for tx in transactions if tx.get("to_address") == address
                    ]
                    vasp_data[address] = normalized
                    attribution = VASPAttribution(
                        case_id=case.id,
                        wallet_address=address,
                        entity_name=vasp["entity_name"],
                        entity_type=vasp.get("entity_type"),
                        attribution_type=normalized["attribution_type"],
                        confidence=AttributionConfidence(normalized["confidence"]),
                        source=normalized["source"],
                        supporting_evidence=normalized["supporting_evidence"],
                        attribution_status=normalized["attribution_status"],
                        provenance=normalized["provenance"],
                        source_reference=normalized["source_reference"],
                        reasoning=normalized["reasoning"],
                        supporting_transaction_hashes=normalized["supporting_transaction_hashes"],
                    )
                    self.db.add(attribution)
        return vasp_data

    async def _save_risk_assessments(self, case: Case, risk_results: Dict):
        """Persist risk assessments."""
        for address, risk in risk_results.items():
            rc = risk.get("risk_category", "low")
            risk_cat = RiskCategory(rc) if rc in [e.value for e in RiskCategory] else RiskCategory.LOW
            assessment = RiskAssessment(
                case_id=case.id,
                wallet_address=address,
                risk_score=risk["risk_score"],
                risk_category=risk_cat,
                contributing_signals=risk.get("contributing_signals", []),
                explanation=risk.get("explanation", ""),
            )
            self.db.add(assessment)

    async def _generate_evidence(
        self,
        case: Case,
        findings: List[Dict],
        finding_records: List[PatternFinding],
        risk_results: Dict,
        vasp_data: Dict,
        transactions: List[Dict],
    ):
        """Generate evidence items from findings, risk, and attributions."""
        # Evidence from pattern findings
        for f, finding_record in zip(findings, finding_records):
            evidence = Evidence(
                case_id=case.id,
                finding_id=finding_record.id,
                evidence_type="pattern",
                title=f["pattern_name"],
                description=f["description"],
                reason=f.get("trigger"),
                transaction_hash=f.get("supporting_transaction_ids", [None])[0] if f.get("supporting_transaction_ids") else None,
                wallet_address=f.get("affected_wallets", [None])[0] if f.get("affected_wallets") else None,
                source="pattern_engine",
            )
            self.db.add(evidence)

        # Evidence from VASP attributions
        for address, vasp in vasp_data.items():
            evidence = Evidence(
                case_id=case.id,
                evidence_type="attribution",
                title=f"VASP Attribution: {vasp['entity_name']}",
                description=(
                    f"Wallet {address[:12]}... attributed to {vasp['entity_name']} "
                    f"({vasp.get('attribution_type', 'unknown')} status; {vasp.get('confidence', 'unknown')} confidence). "
                    f"Source: {vasp.get('source', 'unknown')}. "
                    f"{vasp.get('supporting_evidence', '')}"
                ),
                reason=(
                    f"Wallet has {vasp.get('attribution_status', 'unknown')} attribution "
                    f"to {vasp['entity_name']}; source: {vasp.get('source_reference') or vasp.get('source', 'unknown')}."
                ),
                wallet_address=address,
                source="vasp_attribution",
            )
            self.db.add(evidence)
            await self.db.flush()
            vasp["supporting_evidence_ids"] = [str(evidence.id)]
            attribution_result = await self.db.execute(
                select(VASPAttribution).where(
                    VASPAttribution.case_id == case.id,
                    VASPAttribution.wallet_address == address,
                ).order_by(VASPAttribution.created_at.desc())
            )
            attribution_record = attribution_result.scalars().first()
            if attribution_record:
                attribution_record.supporting_evidence_ids = [str(evidence.id)]

        # Evidence from high-risk wallets
        for address, risk in risk_results.items():
            if risk["risk_score"] >= 50:
                evidence = Evidence(
                    case_id=case.id,
                    evidence_type="risk",
                    title=f"High Risk Wallet: {address[:12]}...",
                    description=risk.get("explanation", "High risk score detected"),
                    reason=f"Risk score: {risk['risk_score']}/100 ({risk['risk_category']})",
                    wallet_address=address,
                    source="risk_engine",
                )
                self.db.add(evidence)

    async def _build_timeline(self, case: Case, transactions: List[Dict], findings: List[Dict]):
        """Build chronological investigation timeline from transactions and findings."""
        events = []

        # Transaction events
        for i, tx in enumerate(sorted(transactions, key=lambda t: t.get("timestamp", datetime.min))):
            ts = tx.get("timestamp")
            if not ts:
                continue
            events.append({
                "event_type": "transaction",
                "title": f"Fund Transfer: {tx['amount']:.4f} {tx.get('asset', 'ETH')}",
                "description": (
                    f"From {tx['from_address'][:12]}... to {tx['to_address'][:12]}... "
                    f"({tx['amount']:.4f} {tx.get('asset', 'ETH')})"
                ),
                "timestamp": ts,
                "transaction_hash": tx.get("hash"),
                "from_address": tx["from_address"],
                "to_address": tx["to_address"],
                "amount": tx["amount"],
                "asset": tx.get("asset", "ETH"),
            })

        # Sort by timestamp
        events.sort(key=lambda e: e["timestamp"])

        # Save to DB with sequence order
        for i, event in enumerate(events):
            inv_event = InvestigationEvent(
                case_id=case.id,
                event_type=event["event_type"],
                title=event["title"],
                description=event.get("description"),
                timestamp=event["timestamp"],
                transaction_hash=event.get("transaction_hash"),
                from_address=event.get("from_address"),
                to_address=event.get("to_address"),
                amount=event.get("amount"),
                asset=event.get("asset"),
                sequence_order=i,
            )
            self.db.add(inv_event)

    async def _save_fund_flows(self, case: Case, transactions: List[Dict], primary_path: List[str]):
        """Save fund flow records along the primary path."""
        path_set = set()
        for i in range(len(primary_path) - 1):
            path_set.add((primary_path[i], primary_path[i + 1]))

        sorted_txs = sorted(transactions, key=lambda t: t.get("timestamp", datetime.min))

        for idx, tx in enumerate(sorted_txs):
            is_primary = (tx["from_address"], tx["to_address"]) in path_set
            flow = FundFlow(
                case_id=case.id,
                path_index=idx,
                from_address=tx["from_address"],
                to_address=tx["to_address"],
                amount=tx["amount"],
                asset=tx.get("asset", "ETH"),
                hop_number=tx.get("hop_number", 0),
                timestamp=tx["timestamp"],
                transaction_hash=tx["hash"],
                is_primary_path=is_primary,
            )
            self.db.add(flow)

    async def get_graph_data(self, case_id: str) -> Dict[str, Any]:
        """Retrieve graph data for a case from DB."""
        case = await self.db.get(Case, uuid.UUID(case_id))
        if not case:
            raise ValueError(f"Case {case_id} not found")

        # Fetch transactions and wallets
        tx_result = await self.db.execute(
            select(Transaction).where(Transaction.case_id == case.id)
        )
        transactions = tx_result.scalars().all()

        w_result = await self.db.execute(
            select(Wallet).where(Wallet.case_id == case.id)
        )
        wallets = w_result.scalars().all()

        # Build graph from DB records
        tx_dicts = [
            {
                "hash": t.hash,
                "from_address": t.from_address,
                "to_address": t.to_address,
                "amount": t.amount,
                "asset": t.asset,
                "timestamp": t.timestamp,
                "is_suspicious": t.is_suspicious,
                "hop_number": t.hop_number,
            }
            for t in transactions
        ]

        wallet_dict = {
            w.address: {
                "label": w.label,
                "is_reported": w.is_reported,
                "is_intermediary": w.is_intermediary,
                "is_destination": w.is_destination,
                "is_suspicious": w.is_suspicious,
                "hop_distance": w.hop_distance,
                "total_received": w.total_received,
                "total_sent": w.total_sent,
                "transaction_count": w.transaction_count,
            }
            for w in wallets
        }

        # Build and serialize
        self.graph_engine.build_graph(tx_dicts, wallet_dict)
        reported_wallet = case.reported_wallet
        primary_path = self.graph_engine.get_primary_path(reported_wallet)

        # Get risk and vasp data from DB
        risk_result = await self.db.execute(
            select(RiskAssessment).where(RiskAssessment.case_id == case.id)
        )
        risk_records = risk_result.scalars().all()
        risk_data = {
            r.wallet_address: {
                "risk_score": r.risk_score,
                "risk_category": r.risk_category.value if r.risk_category else "low",
                "contributing_signals": r.contributing_signals or [],
            }
            for r in risk_records
        }

        vasp_result = await self.db.execute(
            select(VASPAttribution).where(VASPAttribution.case_id == case.id)
        )
        vasp_records = vasp_result.scalars().all()
        vasp_data = {
            v.wallet_address: normalize_attribution(v)
            for v in vasp_records
        }

        return self.graph_engine.serialize_for_frontend(
            primary_path=primary_path,
            vasp_data=vasp_data,
            risk_data=risk_data,
        )

    async def get_why_explanation(self, case_id: str, wallet_address: str) -> Dict[str, Any]:
        """Generate WHY? explanation for a specific wallet."""
        case_uuid = uuid.UUID(case_id)

        # Get findings involving this wallet
        findings_result = await self.db.execute(
            select(PatternFinding).where(PatternFinding.case_id == case_uuid)
        )
        all_findings = findings_result.scalars().all()
        wallet_findings = [
            f for f in all_findings
            if wallet_address in (f.affected_wallets or [])
        ]

        # Get evidence
        evidence_result = await self.db.execute(
            select(Evidence).where(
                Evidence.case_id == case_uuid,
                Evidence.wallet_address == wallet_address,
            )
        )
        evidence_items = evidence_result.scalars().all()

        # Get risk
        risk_result = await self.db.execute(
            select(RiskAssessment).where(
                RiskAssessment.case_id == case_uuid,
                RiskAssessment.wallet_address == wallet_address,
            )
        )
        risk = risk_result.scalars().first()

        # Build reasons
        reasons = []
        for f in wallet_findings:
            reasons.append(f.description)
        if risk and risk.risk_score >= 25:
            reasons.append(f"Risk Score: {risk.risk_score}/100 ({risk.risk_category.value})")
        for e in evidence_items:
            if e.reason and e.reason not in reasons:
                reasons.append(e.reason)

        if not reasons:
            reasons.append("No significant flags detected for this wallet.")

        return {
            "wallet_address": wallet_address,
            "reasons": reasons,
            "findings": [
                {
                    "id": str(f.id),
                    "pattern_type": f.pattern_type.value,
                    "pattern_name": f.pattern_name,
                    "description": f.description,
                    "severity": f.severity.value,
                    "confidence": f.confidence,
                    "trigger": f.trigger,
                    "affected_wallets": f.affected_wallets,
                    "supporting_transaction_ids": f.supporting_transaction_ids,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in wallet_findings
            ],
            "evidence": [
                {
                    "id": str(e.id),
                    "evidence_type": e.evidence_type,
                    "title": e.title,
                    "description": e.description,
                    "reason": e.reason,
                    "transaction_hash": e.transaction_hash,
                    "wallet_address": e.wallet_address,
                    "source": e.source,
                    "is_bookmarked": e.is_bookmarked,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in evidence_items
            ],
            "risk": {
                "wallet_address": wallet_address,
                "risk_score": risk.risk_score if risk else 0,
                "risk_category": risk.risk_category.value if risk else "low",
                "contributing_signals": risk.contributing_signals if risk else [],
                "explanation": risk.explanation if risk else "No risk assessment available.",
            } if risk else None,
        }

    async def get_replay_events(self, case_id: str) -> List[Dict[str, Any]]:
        """Generate replay events in chronological order."""
        case_uuid = uuid.UUID(case_id)

        events_result = await self.db.execute(
            select(InvestigationEvent)
            .where(InvestigationEvent.case_id == case_uuid)
            .order_by(InvestigationEvent.sequence_order)
        )
        events = events_result.scalars().all()

        replay_events = []
        cumulative = 0.0

        for i, event in enumerate(events):
            amount = event.amount or 0
            cumulative += amount

            highlight_nodes = []
            highlight_edges = []
            if event.from_address:
                highlight_nodes.append(event.from_address)
            if event.to_address:
                highlight_nodes.append(event.to_address)
            if event.from_address and event.to_address:
                highlight_edges.append(
                    f"{event.from_address}-{event.to_address}-{(event.transaction_hash or '')[:8]}"
                )

            replay_events.append({
                "event_id": event.id,
                "step": i + 1,
                "event_type": event.event_type,
                "title": event.title,
                "description": event.description or "",
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "from_address": event.from_address,
                "to_address": event.to_address,
                "amount": event.amount,
                "asset": event.asset,
                "transaction_hash": event.transaction_hash,
                "highlight_nodes": highlight_nodes,
                "highlight_edges": highlight_edges,
                "cumulative_amount": round(cumulative, 4),
            })

        return replay_events
