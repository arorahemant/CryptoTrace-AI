from app.core.transfers import record_fields
from app.services.destination_service import destination_context
"""
CryptoTrace AI - AI Investigation Copilot Service
Case-specific, grounded AI assistant.
NOT a generic chatbot — only answers from structured case data.
"""
import logging
from typing import Dict, Any, List, Optional
import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import (
    Case, Transaction, Wallet, PatternFinding,
    Evidence, RiskAssessment,
    AIConversation, FundFlow,
)

logger = logging.getLogger(__name__)


class AIService:
    """
    Grounded AI Investigation Copilot.
    Generates case-specific answers from structured investigation data.
    Uses local structured analysis in every environment.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def query(self, case_id: str, question: str, wallet_address=None, finding_id=None) -> Dict[str, Any]:
        """
        Process an investigator's question about a case.
        Uses structured case data to generate a grounded answer.
        """
        case_uuid = uuid.UUID(case_id)

        # Build structured context from case data
        context = await self._build_context(case_uuid)

        if not context:
            if self._is_greeting(question) or self._is_capability_question(question):
                return self._welcome_answer(context_available=False)
            return {
                "answer": "Case context is unavailable. Run the investigation before asking about the money trail, findings, or evidence.",
                "grounded": True,
                "sources": [],
                "suggested_questions": [
                    "Run the investigation to generate analysis data."
                ],
            }

        explicit_addresses = re.findall(r'0x[0-9a-fA-F]{40}\b', question)
        context['selected_wallet'] = wallet_address or (explicit_addresses[0].lower() if explicit_addresses else None)
        context['selected_finding'] = finding_id
        # Save user question
        user_msg = AIConversation(
            case_id=case_uuid,
            role="user",
            content=question,
        )
        self.db.add(user_msg)

        # Refuse identity, off-case, and future-fact requests before any model
        # call. A prompt is not a sufficient evidence source, even when an
        # external LLM is configured.
        if self._is_unsupported_question(question):
            answer_data = self._unsupported_answer(context)
        elif self._is_greeting(question) or self._is_capability_question(question):
            answer_data = self._welcome_answer(context_available=True, context=context)
        elif not self._has_supported_intent(question):
            answer_data = self._scope_answer(context)
        else:
            answer_data = self._generate_structured_answer(question, context)

        intelligence = context.get('destination_intelligence') or {}
        answer_data.update(run_id=context['run_id'], destination=context.get('destination'),
            attribution_status=(intelligence.get('attribution') or {}).get('attribution_status', 'unknown'),
            data_origin='demo' if context['case']['is_demo'] else 'observed', coverage=context.get('coverage'),
            limitations=intelligence.get('limitations', []))
        # Save assistant response
        assistant_msg = AIConversation(
            case_id=case_uuid,
            role="assistant",
            content=answer_data["answer"],
            grounding_context={"sources": answer_data.get("sources", []), 'run_id': context['run_id'], 'supporting_records': answer_data.get('supporting_records', [])},
        )
        self.db.add(assistant_msg)

        answer_data["output_kind"] = "deterministic_explanation"
        return answer_data

    @staticmethod
    def _is_unsupported_question(question: str) -> bool:
        question_lower = question.lower().replace("’", "'")
        unsupported_markers = (
            "who owns", "owner of", "criminal", "victim's identity", "victim identity",
            "bank account", "not in the case", "not in this case", "does not exist",
            "doesn't exist", "not observed", "outside this case", "invent a transaction",
            "make up a transaction", "after the last", "after the latest", "latest event",
            "future transaction", "future event", "freeze wallet", "freeze status", "government action", "frozen", "custody confirmed",
        )
        return any(marker in question_lower for marker in unsupported_markers)

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.lower().strip().replace("?", "").replace("!", "").split())

    @classmethod
    def _is_greeting(cls, question: str) -> bool:
        normalized = cls._normalize_question(question)
        return normalized in {
            "hello", "hi", "hey", "hello there", "hi there",
            "good morning", "good afternoon", "good evening",
        }

    @classmethod
    def _is_capability_question(cls, question: str) -> bool:
        normalized = cls._normalize_question(question)
        return normalized in {
            "what can you do", "how can you help", "help",
            "what do you do", "what can i ask",
        }

    @classmethod
    def _has_supported_intent(cls, question: str) -> bool:
        question_lower = cls._normalize_question(question)
        supported_markers = (
            "where", "money", "trail", "flow", "path", "transaction", "transfer",
            "why", "flag", "suspicious", "pattern", "reason", "support", "evidence",
            "intermediar", "wallet", "risk", "score", "vasp", "exchange", "attribute",
            "entity", "destination", "summary", "summarize", "overview", "report",
            "what happened", "explain", "simple", "next", "investigate", "missing", "attribution",
        )
        return any(marker in question_lower for marker in supported_markers)

    def _welcome_answer(
        self,
        context_available: bool,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        availability = (
            "This case's investigation context is available."
            if context_available
            else "This case does not have investigation context yet."
        )
        return {
            "answer": (
                "Hello. I’m the CryptoTrace investigation copilot. I can explain this case, "
                "walk through the money trail, or point you to the evidence supporting a finding. "
                f"{availability} I only answer from case-scoped records and deterministic analysis."
            ),
            "grounded": True,
            "sources": ["case_data"] if context_available else [],
            "suggested_questions": self._get_suggested_questions(context or {}),
        }

    def _scope_answer(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "answer": (
                "That question is outside this investigation’s available case context. "
                "I can summarize the case, explain the money trail, identify recorded patterns "
                "and intermediary wallets, or point to supporting evidence."
            ),
            "grounded": True,
            "sources": ["case_data"],
            "suggested_questions": self._get_suggested_questions(context),
        }

    def _unsupported_answer(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "answer": "Insufficient evidence to determine this confidently. I can only answer from observed transactions, deterministic analysis, and saved case evidence.",
            "grounded": True,
            "sources": ["case_data"],
            "suggested_questions": self._get_suggested_questions(context),
        }

    async def _build_context(self, case_uuid) -> Optional[Dict[str, Any]]:
        """Build structured context from case investigation data."""
        case = await self.db.get(Case, case_uuid)
        from app.core.capabilities import current_observation
        if not case or not current_observation(case):
            return None

        # Fetch wallets
        w_result = await self.db.execute(
            select(Wallet).where(Wallet.case_id == case_uuid)
        )
        wallets = w_result.scalars().all()

        # Fetch transactions
        tx_result = await self.db.execute(
            select(Transaction).where(Transaction.case_id == case_uuid).order_by(Transaction.timestamp, Transaction.hash, Transaction.id)
        )
        transactions = tx_result.scalars().all()

        # Fetch findings
        f_result = await self.db.execute(
            select(PatternFinding).where(PatternFinding.case_id == case_uuid)
        )
        findings = f_result.scalars().all()

        # Fetch evidence
        e_result = await self.db.execute(
            select(Evidence).where(Evidence.case_id == case_uuid)
        )
        evidence = [e for e in e_result.scalars().all() if case.blockchain.value == "demo" or (e.metadata_ or {}).get("run_id") == (case.analysis_summary or {}).get("run_id")]

        # Fetch risk
        r_result = await self.db.execute(
            select(RiskAssessment).where(RiskAssessment.case_id == case_uuid)
        )
        risk_assessments = r_result.scalars().all()

        # Fetch fund flows
        ff_result = await self.db.execute(
            select(FundFlow)
            .where(FundFlow.case_id == case_uuid)
            .order_by(FundFlow.hop_number)
        )
        from app.services.investigation_service import InvestigationService
        graph = await InvestigationService(self.db).get_graph_data(str(case_uuid))
        from app.services.recommendation_service import build_recommendations
        recommendations = await build_recommendations(self.db, case)
        route = graph["primary_path"]
        pairs = set(zip(route, route[1:]))
        fund_flows = [flow for flow in ff_result.scalars().all() if (flow.from_address, flow.to_address) in pairs]

        if not wallets and not transactions:
            return None

        return {
            'destination_intelligence': graph['destination_intelligence'],
            'recommendations': recommendations,
            "destination": (await destination_context(self.db, case))["selected"],
            "coverage": (case.analysis_summary or {}).get("stats", {}).get("coverage"),
            "run_id": (case.analysis_summary or {}).get("run_id") or f"legacy:{case.id}",
            "case": {
                "case_number": case.case_number,
                "title": case.title,
                "reported_wallet": case.reported_wallet,
                "blockchain": case.blockchain.value if case.blockchain else "unknown",
                "status": case.status.value if case.status else "unknown",
                "reported_amount": case.reported_amount,
                "is_demo": case.is_demo,
            },
            "wallets": [
                {
                    "address": w.address,
                    "label": w.label,
                    "is_reported": w.is_reported,
                    "is_intermediary": w.is_intermediary,
                    "is_destination": w.is_destination,
                    "is_suspicious": w.is_suspicious,
                    "hop_distance": w.hop_distance,
                    "total_received": w.total_received,
                    "total_sent": w.total_sent,
                }
                for w in wallets
            ],
            "transactions_count": len(transactions),
            "key_transactions": [
                {
                    **record_fields(t),
                    "hash": t.hash,
                    "from": t.from_address,
                    "to": t.to_address,
                    "amount": t.amount,
                    "asset": t.asset,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    "hop": t.hop_number,
                }
                for t in transactions
            ],
            "findings": [
                {
                    "id": str(f.id),
                    "pattern": f.pattern_name,
                    "description": f.description,
                    "severity": f.severity.value if f.severity else "medium",
                    "confidence": f.confidence,
                    "trigger": f.trigger,
                    "supporting_transactions": f.supporting_transaction_ids or [],
                    'supporting_transfer_ids': (f.metadata_ or {}).get('supporting_transfer_ids', []),
                    "affected_wallets": f.affected_wallets or [],
                }
                for f in findings
            ],
            "evidence_count": len(evidence),
            "evidence": [
                {
                    'id': str(item.id),
                    'transfer_id': (item.metadata_ or {}).get('transfer_id'),
                    "title": item.title,
                    "reason": item.reason,
                    "transaction_hash": item.transaction_hash,
                    "finding_id": str(item.finding_id) if item.finding_id else None,
                    "source": item.source,
                }
                for item in evidence
            ],
            "risk_assessments": [
                {
                    "wallet": r.wallet_address,
                    "score": r.risk_score,
                    "category": r.risk_category.value if r.risk_category else "low",
                    "explanation": r.explanation,
                }
                for r in risk_assessments
            ],
            "vasp_attributions": [
                {
                    **v, "wallet": address, "entity": v['entity_name'],
                }
                for address, v in (await destination_context(self.db, case))['attributions'].items()
            ],
            "fund_flow_path": [
                {
                    **record_fields(ff),
                    "asset": ff.asset,
                    "from": ff.from_address,
                    "to": ff.to_address,
                    "amount": ff.amount,
                    "hop": ff.hop_number,
                }
                for ff in fund_flows
            ],
        }

    async def _query_llm(self, question: str, context: Dict) -> Dict[str, Any]:
        """Compatibility entry point: always local, including configured environments."""
        return self._generate_structured_answer(question, context)

    def _generate_structured_answer(self, question: str, context: Dict) -> Dict[str, Any]:
        if self._is_unsupported_question(question):
            return self._unsupported_answer(context)
        from app.services.copilot_service import explain
        return explain(question, context)

    def _get_suggested_questions(self, context: Dict) -> List[str]:
        from app.services.copilot_service import QUESTIONS
        return QUESTIONS
