from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "get",
    "got",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "let",
    "lets",
    "like",
    "me",
    "more",
    "my",
    "now",
    "of",
    "on",
    "or",
    "our",
    "out",
    "so",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "up",
    "us",
    "was",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
}

FINANCE_TERMS = {
    "alpha",
    "apy",
    "arb",
    "bearish",
    "bridge",
    "btc",
    "bullish",
    "catalyst",
    "crypto",
    "dao",
    "defi",
    "eth",
    "floor",
    "governance",
    "inflation",
    "liquidity",
    "macro",
    "market",
    "mint",
    "nft",
    "onchain",
    "portfolio",
    "price",
    "resistance",
    "risk",
    "rwa",
    "sentiment",
    "sol",
    "staking",
    "support",
    "supply",
    "token",
    "tokenomics",
    "treasury",
    "volatility",
    "volume",
    "wallet",
    "web3",
    "yield",
}

WEB3_TERMS = {
    "airdrop",
    "blockchain",
    "bridge",
    "dao",
    "defi",
    "governance",
    "layer2",
    "mainnet",
    "marketplace",
    "memecoin",
    "mint",
    "nft",
    "opensea",
    "rollup",
    "smartcontract",
    "solana",
    "staking",
    "tokenomics",
    "wallet",
    "web3",
}

POSITIVE_WORDS = {"bullish", "clean", "funny", "good", "great", "sharp", "strong", "up", "win"}
NEGATIVE_WORDS = {"bad", "bearish", "crash", "cope", "down", "dump", "rug", "scam", "weak"}
HUMOR_CUES = {"funny", "haha", "humor", "joke", "lol", "lmao", "meme", "roast", "wit", "witty"}

RISK_PATTERNS = (
    re.compile(r"\b(guaranteed?|risk[- ]?free|sure thing|no downside)\b", re.IGNORECASE),
    re.compile(r"\b(100x|10x|moonshot|ape in|all in)\b", re.IGNORECASE),
    re.compile(r"\b(insider|front[- ]?run|wash trade|pump and dump)\b", re.IGNORECASE),
    re.compile(r"\b(leverage|leveraged|liquidation)\b", re.IGNORECASE),
)

QUESTION_WORDS = {"what", "why", "how", "when", "where", "who", "which"}
RESEARCH_CUES = {"explain", "compare", "analyze", "breakdown", "clarify", "walkthrough"}


@dataclass(frozen=True)
class TextAnalysis:
    text: str
    sentences: list[str]
    tokens: list[str]
    keywords: list[str]
    intents: list[str]
    finance_entities: list[str]
    web3_entities: list[str]
    humor_signals: list[str]
    risk_flags: list[str]
    sentiment: str
    finance_score: float
    humor_score: float
    complexity_score: float
    question_count: int

    def prompt_summary(self) -> str:
        intents = ", ".join(self.intents) or "general_discussion"
        keywords = ", ".join(self.keywords[:5]) or "none"
        finance = ", ".join(self.finance_entities[:5]) or "none"
        risk = ", ".join(self.risk_flags[:3]) or "none"
        return (
            f"intents={intents}; keywords={keywords}; finance={finance}; "
            f"sentiment={self.sentiment}; risk={risk}"
        )


class LocalNLPEngine:
    def normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def analyze(self, text: str) -> TextAnalysis:
        normalized = self.normalize(text)
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
        tokens = re.findall(r"[A-Za-z0-9$#@][A-Za-z0-9$#@'._-]*", normalized)
        lower_tokens = [token.lower() for token in tokens]

        keyword_counter = Counter(
            token
            for token in lower_tokens
            if len(token) > 2 and token not in STOPWORDS and not token.isdigit()
        )
        keywords = [token for token, _count in keyword_counter.most_common(8)]

        finance_entities = sorted(
            {
                token.upper() if token.startswith("$") else token
                for token in lower_tokens
                if token in FINANCE_TERMS or token.startswith("$")
            }
        )
        web3_entities = sorted({token for token in lower_tokens if token in WEB3_TERMS})
        humor_signals = sorted({cue for cue in HUMOR_CUES if cue in normalized.lower()})

        risk_flags: list[str] = []
        for pattern in RISK_PATTERNS:
            risk_flags.extend(sorted({match.group(0).lower() for match in pattern.finditer(normalized)}))

        finance_hits = len(finance_entities) + len(web3_entities)
        number_hits = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", normalized))
        finance_score = min(1.0, round((finance_hits * 1.6 + number_hits * 0.4) / max(len(tokens), 1) * 6, 3))
        humor_score = min(
            1.0,
            round((len(humor_signals) + normalized.count("!") * 0.2 + normalized.lower().count("lol")) / 3.0, 3),
        )

        sentiment_score = sum(token in POSITIVE_WORDS for token in lower_tokens) - sum(
            token in NEGATIVE_WORDS for token in lower_tokens
        )
        if sentiment_score > 0:
            sentiment = "positive"
        elif sentiment_score < 0:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        question_count = normalized.count("?")
        jargon_hits = sum(token in FINANCE_TERMS or token in WEB3_TERMS for token in lower_tokens)
        complexity_score = min(
            1.0,
            round((len(set(lower_tokens)) * 0.03) + (jargon_hits * 0.05) + (question_count * 0.08), 3),
        )

        intents: list[str] = []
        if finance_score >= 0.25:
            intents.append("market_analysis")
        if question_count or any(token in QUESTION_WORDS for token in lower_tokens[:4]):
            intents.append("question_answering")
        if any(cue in lower_tokens for cue in RESEARCH_CUES):
            intents.append("research")
        if humor_score >= 0.3:
            intents.append("humor")
        if risk_flags:
            intents.append("risk_review")
        if not intents:
            intents.append("general_discussion")

        return TextAnalysis(
            text=normalized,
            sentences=sentences,
            tokens=tokens,
            keywords=keywords,
            intents=intents,
            finance_entities=finance_entities,
            web3_entities=web3_entities,
            humor_signals=humor_signals,
            risk_flags=risk_flags,
            sentiment=sentiment,
            finance_score=finance_score,
            humor_score=humor_score,
            complexity_score=complexity_score,
            question_count=question_count,
        )


__all__ = ["LocalNLPEngine", "TextAnalysis"]
