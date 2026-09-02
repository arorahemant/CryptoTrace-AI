"""
CryptoTrace AI - AI Investigation Copilot Service
Case-specific, grounded AI assistant.
NOT a generic chatbot — only answers from structured case data.
"""
import logging
from typing import Dict, Any, List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import (
    Case, Transaction, Wallet, PatternFinding,
    Evidence, RiskAssessment, VASPAttribution,
    AIConversation, FundFlow,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """
    Grounded AI Investigation Copilot.
    Generates case-specific answers from structured investigation data.
    Falls back to structured analysis if no LLM API key is available.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def query(self, case_id: str, question: str) -> Dict[str, Any]:
        """
        Process an investigator's question about a case.
        Uses structured case data to generate a grounded answer.
        """
        case_uuid = uuid.UUID(case_id)

        # Build structured context from case data
        context = await self._build_context(case_uuid)

        if not context:
            return {
                "answer": "No investigation data available for this case. Please run the investigation first.",
                "grounded": True,
                "sources": [],
                "suggested_questions": [
                    "Run the investigation to generate analysis data."
                ],
            }

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
        elif settings.OPENAI_API_KEY:
            answer_data = await self._query_llm(question, context)
        else:
            answer_data = self._generate_structured_answer(question, context)

        # Save assistant response
        assistant_msg = AIConversation(
            case_id=case_uuid,
            role="assistant",
            content=answer_data["answer"],
            grounding_context={"sources": answer_data.get("sources", [])},
        )
        self.db.add(assistant_msg)

        return answer_data

    @staticmethod
    def _is_unsupported_question(question: str) -> bool:
        question_lower = question.lower().replace("’", "'")
        unsupported_markers = (
            "who owns", "owner of", "criminal", "victim's identity", "victim identity",
            "bank account", "not in the case", "not in this case", "does not exist",
            "doesn't exist", "not observed", "outside this case", "invent a transaction",
            "make up a transaction", "after the last", "after the latest", "latest event",
            "future transaction", "future event",
        )
        return any(marker in question_lower for marker in unsupported_markers)

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
        if not case:
            return None

        # Fetch wallets
        w_result = await self.db.execute(
            select(Wallet).where(Wallet.case_id == case_uuid)
        )
        wallets = w_result.scalars().all()

        # Fetch transactions
        tx_result = await self.db.execute(
            select(Transaction).where(Transaction.case_id == case_uuid).limit(50)
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
        evidence = e_result.scalars().all()

        # Fetch risk
        r_result = await self.db.execute(
            select(RiskAssessment).where(RiskAssessment.case_id == case_uuid)
        )
        risk_assessments = r_result.scalars().all()

        # Fetch VASP
        v_result = await self.db.execute(
            select(VASPAttribution).where(VASPAttribution.case_id == case_uuid)
        )
        vasps = v_result.scalars().all()

        # Fetch fund flows
        ff_result = await self.db.execute(
            select(FundFlow)
            .where(FundFlow.case_id == case_uuid, FundFlow.is_primary_path == True)
            .order_by(FundFlow.hop_number)
        )
        fund_flows = ff_result.scalars().all()

        if not wallets and not transactions:
            return None

        return {
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
                    "hash": t.hash,
                    "from": t.from_address,
                    "to": t.to_address,
                    "amount": t.amount,
                    "asset": t.asset,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    "hop": t.hop_number,
                }
                for t in transactions[:20]
            ],
            "findings": [
                {
                    "pattern": f.pattern_name,
                    "description": f.description,
                    "severity": f.severity.value if f.severity else "medium",
                    "confidence": f.confidence,
                }
                for f in findings
            ],
            "evidence_count": len(evidence),
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
                    "wallet": v.wallet_address,
                    "entity": v.entity_name,
                    "confidence": v.confidence.value if v.confidence else "unknown",
                    "source": v.source,
                }
                for v in vasps
            ],
            "fund_flow_path": [
                {
                    "from": ff.from_address,
                    "to": ff.to_address,
                    "amount": ff.amount,
                    "hop": ff.hop_number,
                }
                for ff in fund_flows
            ],
        }

    async def _query_llm(self, question: str, context: Dict) -> Dict[str, Any]:
        """Query LLM with structured case context."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            system_prompt = (
                "You are CryptoTrace AI Investigation Copilot. You ONLY answer questions "
                "using the provided structured case data. You MUST NOT invent transaction hashes, "
                "wallet addresses, amounts, timestamps, VASP ownership, evidence, or criminal identities. "
                "If the data is insufficient to answer, say so clearly. "
                "When attribution is uncertain, state the confidence level. "
                "Distinguish between FACT (blockchain record), ANALYSIS (computed signals), "
                "INFERENCE (reasonable interpretation), and your SUMMARY. "
                "Be concise and professional. Reference specific transaction hashes and wallet "
                "addresses from the data when possible."
            )

            context_str = self._format_context_for_llm(context)

            response = await client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"CASE DATA:\n{context_str}\n\nQUESTION: {question}"},
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            answer = response.choices[0].message.content

            return {
                "answer": answer,
                "grounded": True,
                "sources": ["case_data", "investigation_analysis"],
                "suggested_questions": self._get_suggested_questions(context),
            }
        except Exception:
            logger.error("LLM query failed; falling back to structured analysis")
            return self._generate_structured_answer(question, context)

    def _generate_structured_answer(self, question: str, context: Dict) -> Dict[str, Any]:
        """
        Generate structured answer without LLM.
        Uses pattern matching on the question to select relevant context.
        DEMO MODE: Clearly labeled as structured analysis, not AI generation.
        """
        question_lower = question.lower()
        answer_parts = []
        sources = []

        # Refuse requests that require identity, criminality, off-case data, or
        # future facts. These are outside the structured evidence boundary.
        if self._is_unsupported_question(question):
            return self._unsupported_answer(context)

        case = context.get("case", {})
        answer_parts.append(
            f"📋 **Case {case.get('case_number', 'N/A')}** — {case.get('title', 'Investigation')}"
        )

        if case.get("is_demo"):
            answer_parts.append("\n⚠️ *DEMO MODE: This analysis is based on demonstration data.*\n")

        # Money trail questions
        if any(kw in question_lower for kw in ["where", "money", "go", "trail", "flow", "path"]):
            fund_flow = context.get("fund_flow_path", [])
            if fund_flow:
                answer_parts.append("**Fund Flow Path (Primary Trail):**")
                for step in fund_flow:
                    answer_parts.append(
                        f"  → {step['from'][:12]}... → {step['to'][:12]}... "
                        f"({step['amount']:.4f} ETH, hop {step['hop']})"
                    )
                sources.append("fund_flow_analysis")
            else:
                answer_parts.append("Fund flow data is not yet available. Run the investigation first.")

        # Why flagged questions
        if any(kw in question_lower for kw in ["why", "flag", "suspicious", "reason"]):
            findings = context.get("findings", [])
            if findings:
                answer_parts.append("**Suspicious Patterns Detected:**")
                for f in findings:
                    answer_parts.append(
                        f"  • **{f['pattern']}** (severity: {f['severity']}, "
                        f"confidence: {f['confidence']:.0%}): {f['description']}"
                    )
                sources.append("pattern_analysis")

        # Transaction/evidence support questions
        if any(kw in question_lower for kw in ["transaction", "support", "evidence"]):
            transactions = context.get("key_transactions", [])
            if transactions:
                answer_parts.append("**Observed supporting transactions:**")
                for tx in transactions[:10]:
                    answer_parts.append(
                        f"  • {tx['hash']} — {tx['from'][:12]}... → {tx['to'][:12]}... "
                        f"({tx['amount']:.4f} {tx['asset']}, hop {tx['hop']})"
                    )
                sources.append("transaction_records")

        # Intermediary questions
        if any(kw in question_lower for kw in ["intermediar", "wallet", "important", "key"]):
            wallets = context.get("wallets", [])
            intermediaries = [w for w in wallets if w.get("is_intermediary")]
            if intermediaries:
                answer_parts.append("**Potential Intermediary Wallets:**")
                for w in intermediaries:
                    answer_parts.append(
                        f"  • {w['address'][:12]}... — {w.get('label', 'Unknown')} "
                        f"(received: {w['total_received']:.4f}, sent: {w['total_sent']:.4f})"
                    )
                sources.append("intermediary_analysis")

        # Risk questions
        if any(kw in question_lower for kw in ["risk", "score", "danger", "threat"]):
            risks = context.get("risk_assessments", [])
            high_risk = [r for r in risks if r["score"] >= 25]
            if high_risk:
                answer_parts.append("**Risk Assessments (significant):**")
                for r in sorted(high_risk, key=lambda x: x["score"], reverse=True):
                    answer_parts.append(
                        f"  • {r['wallet'][:12]}...: **{r['category'].upper()}** "
                        f"(score: {r['score']}/100)"
                    )
                sources.append("risk_analysis")

        # VASP / exchange questions
        if any(kw in question_lower for kw in ["vasp", "exchange", "attribute", "entity", "destination"]):
            vasps = context.get("vasp_attributions", [])
            if vasps:
                answer_parts.append("**VASP Attributions:**")
                for v in vasps:
                    answer_parts.append(
                        f"  • {v['wallet'][:12]}...: {v['entity']} "
                        f"(confidence: {v['confidence']}, source: {v['source']})"
                    )
                sources.append("vasp_attribution")

        # Summary / general questions
        if any(kw in question_lower for kw in ["summary", "summarize", "overview", "report", "what happened"]):
            answer_parts.append(f"\n**Investigation Summary:**")
            answer_parts.append(f"  • Reported wallet: {case.get('reported_wallet', 'N/A')}")
            answer_parts.append(f"  • Total wallets discovered: {len(context.get('wallets', []))}")
            answer_parts.append(f"  • Total transactions traced: {context.get('transactions_count', 0)}")
            answer_parts.append(f"  • Suspicious patterns: {len(context.get('findings', []))}")
            answer_parts.append(f"  • Evidence items: {context.get('evidence_count', 0)}")

            vasps = context.get("vasp_attributions", [])
            if vasps:
                answer_parts.append(f"  • Destination attribution: {vasps[0]['entity']} ({vasps[0]['confidence']})")
            sources.append("case_summary")

        # Default if no specific match
        if len(answer_parts) <= 2:
            answer_parts.append(
                "Based on the available case data, I can provide information about:\n"
                "• Fund flow and money trail\n"
                "• Suspicious patterns detected\n"
                "• Intermediary wallets\n"
                "• Risk assessments\n"
                "• VASP/exchange attributions\n"
                "• Investigation summary\n\n"
                "Please ask a more specific question about the investigation."
            )

        answer = "\n".join(answer_parts)

        return {
            "answer": answer,
            "grounded": True,
            "sources": sources or ["case_data"],
            "suggested_questions": self._get_suggested_questions(context),
        }

    def _get_suggested_questions(self, context: Dict) -> List[str]:
        """Generate contextually relevant follow-up questions."""
        return [
            "Where did the money go?",
            "Which wallets are potential intermediaries?",
            "What suspicious patterns were detected?",
            "What is the risk assessment?",
            "Summarize the investigation.",
        ]

    def _format_context_for_llm(self, context: Dict) -> str:
        """Format context as a concise string for LLM consumption."""
        parts = []

        case = context.get("case", {})
        parts.append(f"Case: {case.get('case_number')} - {case.get('title')}")
        parts.append(f"Reported Wallet: {case.get('reported_wallet')}")
        parts.append(f"Blockchain: {case.get('blockchain')}")
        if case.get("is_demo"):
            parts.append("NOTE: This is DEMO DATA for demonstration purposes.")

        parts.append(f"\nWallets discovered: {len(context.get('wallets', []))}")
        parts.append(f"Transactions traced: {context.get('transactions_count', 0)}")

        # Key findings
        findings = context.get("findings", [])
        if findings:
            parts.append(f"\nSuspicious Patterns ({len(findings)}):")
            for f in findings:
                parts.append(f"  - {f['pattern']}: {f['description']}")

        # VASP
        vasps = context.get("vasp_attributions", [])
        if vasps:
            parts.append("\nVASP Attributions:")
            for v in vasps:
                parts.append(f"  - {v['wallet']}: {v['entity']} ({v['confidence']})")

        # Risk
        risks = context.get("risk_assessments", [])
        if risks:
            parts.append("\nRisk Assessments:")
            for r in sorted(risks, key=lambda x: x["score"], reverse=True)[:5]:
                parts.append(f"  - {r['wallet']}: {r['category']} ({r['score']}/100)")

        # Fund flow
        fund_flow = context.get("fund_flow_path", [])
        if fund_flow:
            parts.append("\nPrimary Fund Flow:")
            for step in fund_flow:
                parts.append(f"  Hop {step['hop']}: {step['from']} → {step['to']} ({step['amount']} ETH)")

        return "\n".join(parts)
