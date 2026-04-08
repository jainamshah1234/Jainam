from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AnalysisResult:
    risky_clauses: list[str]
    suggestions: list[str]
    summary: str
    confidence_score: float


RISK_PATTERNS = {
    "indemnify": "Broad indemnification can create disproportionate liability.",
    "terminate immediately": "Immediate termination rights may create operational risk.",
    "sole discretion": "Sole discretion language may be one-sided and unenforceable in disputes.",
    "unlimited liability": "Unlimited liability can expose client to excessive damages.",
    "governing law": "Ensure governing law and venue align with client interests.",
}


def analyze_legal_text(text: str) -> AnalysisResult:
    normalized = text.lower()
    hits = [explanation for needle, explanation in RISK_PATTERNS.items() if needle in normalized]

    if not hits:
        hits = [
            "No obvious high-risk keywords were detected; manual legal review is still recommended.",
        ]

    suggestions = [
        "Narrow indemnity scope to direct damages and carve out gross negligence/willful misconduct.",
        "Add mutual termination cure periods (e.g., 15-30 days) before termination takes effect.",
        "Cap liability to a negotiated multiple of fees paid under the agreement.",
        "Clarify governing law, dispute venue, and arbitration/mediation sequence.",
    ]

    summary = (
        "This document appears to be a binding agreement with obligations and risk allocation terms. "
        "The highlighted clauses may create legal or commercial imbalance and should be negotiated "
        "for clearer limits, mutuality, and enforceability."
    )

    confidence = min(0.95, 0.55 + 0.08 * len(hits))

    return AnalysisResult(
        risky_clauses=hits,
        suggestions=suggestions,
        summary=summary,
        confidence_score=round(confidence, 2),
    )
