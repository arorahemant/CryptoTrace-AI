"""
CryptoTrace AI - Risk Engine
Deterministic, explainable risk scoring for wallet prioritization.
This is investigation prioritization — NOT legal judgement.
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Deterministic weighted risk scoring.
    Each signal contributes a weighted score. Total is normalized to 0-100.
    """

    # Signal weights (configurable)
    SIGNAL_WEIGHTS = {
        "rapid_movement": 25,
        "fund_splitting": 20,
        "fund_consolidation": 15,
        "layering": 20,
        "repeated_connections": 10,
        "high_centrality": 15,
        "destination_significance": 20,
        "amount_significance": 10,
        "hop_proximity": 5,
    }

    CATEGORY_THRESHOLDS = {
        "critical": 75,
        "high": 50,
        "medium": 25,
        "low": 0,
    }

    def assess_wallet_risk(
        self,
        address: str,
        findings: List[Dict[str, Any]],
        wallet_data: Dict[str, Any],
        vasp_data: Optional[Dict[str, Any]] = None,
        intermediary_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate risk score for a specific wallet.
        Returns score, category, contributing signals, and explanation.
        """
        signals: List[Dict[str, Any]] = []
        total_score = 0.0

        # Check pattern findings involving this wallet
        wallet_findings = [
            f for f in findings
            if address in f.get("affected_wallets", [])
        ]

        for finding in wallet_findings:
            pattern_type = finding.get("pattern_type", "")
            weight = self.SIGNAL_WEIGHTS.get(pattern_type, 5)
            confidence = finding.get("confidence", 0.5)
            contribution = weight * confidence

            signals.append({
                "signal_name": finding.get("pattern_name", pattern_type),
                "description": finding.get("description", ""),
                "weight": weight,
                "score_contribution": round(contribution, 2),
            })
            total_score += contribution

        # Check intermediary significance
        if intermediary_data:
            centrality = intermediary_data.get("centrality", 0)
            if centrality > 0.1:
                weight = self.SIGNAL_WEIGHTS["high_centrality"]
                contribution = weight * min(centrality * 5, 1.0)
                signals.append({
                    "signal_name": "High Network Centrality",
                    "description": (
                        f"This wallet has high betweenness centrality ({centrality:.3f}) "
                        f"in the transaction network, indicating it's a critical node."
                    ),
                    "weight": weight,
                    "score_contribution": round(contribution, 2),
                })
                total_score += contribution

        # Check VASP attribution significance
        if vasp_data:
            weight = self.SIGNAL_WEIGHTS["destination_significance"]
            contribution = weight * 0.8
            signals.append({
                "signal_name": "Attributed Destination",
                "description": (
                    f"This wallet is attributed to {vasp_data.get('entity_name', 'unknown entity')} "
                    f"({vasp_data.get('confidence', 'unknown')} confidence). "
                    f"Funds reaching a known entity is significant for the investigation."
                ),
                "weight": weight,
                "score_contribution": round(contribution, 2),
            })
            total_score += contribution

        # Hop proximity (closer to reported wallet = more relevant)
        hop_dist = wallet_data.get("hop_distance", 0)
        if hop_dist and hop_dist <= 2:
            weight = self.SIGNAL_WEIGHTS["hop_proximity"]
            contribution = weight * (1 - hop_dist / 10)
            signals.append({
                "signal_name": "Close Proximity to Reported Wallet",
                "description": (
                    f"This wallet is {hop_dist} hop(s) from the reported wallet. "
                    f"Closer wallets may be more directly involved."
                ),
                "weight": weight,
                "score_contribution": round(contribution, 2),
            })
            total_score += contribution

        # Normalize score to 0-100
        risk_score = min(100, round(total_score, 1))

        # Determine category
        risk_category = "low"
        for cat, threshold in sorted(
            self.CATEGORY_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if risk_score >= threshold:
                risk_category = cat
                break

        # Generate explanation
        explanation = self._generate_explanation(address, risk_score, risk_category, signals)

        return {
            "wallet_address": address,
            "risk_score": risk_score,
            "risk_category": risk_category,
            "contributing_signals": signals,
            "explanation": explanation,
        }

    def assess_case_risk(
        self,
        wallets: Dict[str, Dict[str, Any]],
        findings: List[Dict[str, Any]],
        vasp_data: Optional[Dict[str, Dict]] = None,
        intermediary_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Assess risk for all wallets in a case."""
        risk_results = {}

        intermediary_map = {}
        if intermediary_data:
            for item in intermediary_data:
                intermediary_map[item["address"]] = item

        for address, wallet in wallets.items():
            vasp = vasp_data.get(address) if vasp_data else None
            intermediary = intermediary_map.get(address)

            risk_results[address] = self.assess_wallet_risk(
                address=address,
                findings=findings,
                wallet_data=wallet,
                vasp_data=vasp,
                intermediary_data=intermediary,
            )

        return risk_results

    def get_overall_risk(self, risk_results: Dict[str, Dict]) -> str:
        """Get the highest risk category across all wallets."""
        categories = [r.get("risk_category", "low") for r in risk_results.values()]
        priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        if not categories:
            return "low"
        return max(categories, key=lambda c: priority.get(c, 0))

    def _generate_explanation(
        self,
        address: str,
        score: float,
        category: str,
        signals: List[Dict],
    ) -> str:
        if not signals:
            return f"No significant risk signals detected for wallet {address[:12]}..."

        top_signals = sorted(signals, key=lambda s: s["score_contribution"], reverse=True)[:3]
        parts = [
            f"Risk assessment for {address[:12]}...: {category.upper()} ({score}/100).",
            "Contributing factors:"
        ]
        for i, sig in enumerate(top_signals, 1):
            parts.append(f"{i}. {sig['signal_name']} (contribution: {sig['score_contribution']:.1f})")

        return " ".join(parts)
