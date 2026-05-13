from __future__ import annotations

from dataclasses import dataclass

from noesis_agent.brain.nlp_engine import TextAnalysis


GLOSSARY = {
    "liquidity": "Track depth, slippage, and who can actually exit size without moving the market.",
    "tokenomics": "Look at unlocks, emissions, treasury behavior, and who holds voting power.",
    "nft": "Separate brand heat from sustained bids, volume, and holder concentration.",
    "staking": "Check whether yield is real cash flow, inflationary subsidy, or unsustainable emissions.",
    "bridge": "Bridge risk is smart contract risk plus operational risk, not just convenience.",
    "dao": "Governance quality matters only if incentives and treasury controls are real.",
    "rwa": "Real-world asset narratives need enforceability, redemption rails, and jurisdiction clarity.",
    "btc": "Bitcoin discussion usually benefits from timeframe clarity and macro context.",
    "eth": "Ethereum analysis usually needs fee demand, L2 flow, and staking dynamics.",
    "sol": "Solana analysis usually needs throughput, reliability, and app-level demand.",
}


@dataclass(frozen=True)
class FinanceInsight:
    active: bool
    focus_areas: list[str]
    glossary_hits: list[str]
    caution_flags: list[str]
    guidance: list[str]
    risk_level: str
    prompt_summary: str


class CryptoFinanceReasoner:
    def analyze(self, analysis: TextAnalysis) -> FinanceInsight:
        active = analysis.finance_score >= 0.2 or bool(analysis.web3_entities)
        matched_terms = [term for term in analysis.finance_entities + analysis.web3_entities if term.lower() in GLOSSARY]
        glossary_hits = [f"{term}: {GLOSSARY[term.lower()]}" for term in matched_terms[:4]]

        focus_areas: list[str] = []
        if any(term in analysis.finance_entities for term in {"btc", "eth", "sol", "$BTC", "$ETH", "$SOL"}):
            focus_areas.append("market structure")
        if any(term in analysis.finance_entities for term in {"nft", "mint", "floor"}):
            focus_areas.append("NFT flow")
        if any(term in analysis.finance_entities for term in {"dao", "governance", "treasury"}):
            focus_areas.append("governance and treasury")
        if any(term in analysis.finance_entities for term in {"staking", "yield", "apy"}):
            focus_areas.append("yield quality")
        if any(term in analysis.finance_entities for term in {"bridge", "wallet", "onchain"}):
            focus_areas.append("on-chain execution risk")
        if not focus_areas and active:
            focus_areas.append("market risk framing")

        caution_flags = list(analysis.risk_flags)
        if active and "question_answering" in analysis.intents:
            caution_flags.append("state timeframe and uncertainty")
        if active and analysis.sentiment == "positive":
            caution_flags.append("avoid hype without downside framing")

        risk_level = "low"
        if caution_flags:
            risk_level = "high" if len(caution_flags) >= 2 else "medium"

        guidance: list[str] = []
        if active:
            guidance.append("Separate narrative strength from liquidity, adoption, and actual cash-flow proxies.")
            guidance.append("Call out timeframe, catalysts, and downside before sounding conviction.")
            guidance.append("Treat financial discussion as analysis, not advice, and keep uncertainty explicit.")
        else:
            guidance.append("Keep answers concrete, fast, and tied to what the room actually asked.")

        prompt_summary = (
            "finance_active="
            f"{active}; focus={', '.join(focus_areas) or 'none'}; "
            f"risk_level={risk_level}; caution={', '.join(caution_flags[:3]) or 'none'}"
        )

        return FinanceInsight(
            active=active,
            focus_areas=focus_areas,
            glossary_hits=glossary_hits,
            caution_flags=caution_flags,
            guidance=guidance,
            risk_level=risk_level,
            prompt_summary=prompt_summary,
        )


__all__ = ["CryptoFinanceReasoner", "FinanceInsight"]
