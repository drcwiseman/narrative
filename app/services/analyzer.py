from __future__ import annotations

import re
from collections import Counter


POSITIVE_WORDS = {
    "good",
    "great",
    "excellent",
    "safe",
    "support",
    "trust",
    "progress",
    "improve",
}
NEGATIVE_WORDS = {
    "bad",
    "fake",
    "fraud",
    "danger",
    "corrupt",
    "hate",
    "crisis",
    "threat",
}
HARMFUL_PATTERNS = [
    r"\bkill\b",
    r"\battack\b",
    r"\bboycott\b",
    r"\bburn\b",
    r"\bpoison\b",
    r"\bfake news\b",
    r"\belection rigged\b",
]
TOPIC_KEYWORDS = {
    "elections": {"vote", "ballot", "election", "poll", "results"},
    "economy": {"jobs", "inflation", "tax", "business", "price"},
    "security": {"crime", "violence", "police", "security", "threat"},
    "health": {"hospital", "doctor", "vaccine", "health", "disease"},
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def score_sentiment(text: str) -> float:
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    pos = sum(1 for token in tokens if token in POSITIVE_WORDS)
    neg = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    score = (pos - neg) / max(len(tokens), 1)
    return round(max(-1.0, min(1.0, score * 4)), 3)


def extract_topic(text: str) -> str:
    tokens = set(_tokenize(text))
    scores: Counter[str] = Counter()
    for topic, keywords in TOPIC_KEYWORDS.items():
        scores[topic] += len(tokens.intersection(keywords))
    if not scores:
        return "general"
    topic, score = scores.most_common(1)[0]
    return topic if score > 0 else "general"


def harmful_claim_score(text: str) -> float:
    lowered = text.lower()
    hits = sum(1 for pattern in HARMFUL_PATTERNS if re.search(pattern, lowered))
    score = min(1.0, hits / max(len(HARMFUL_PATTERNS) / 3, 1))
    if "http" in lowered and ("fake" in lowered or "rigged" in lowered):
        score = min(1.0, score + 0.2)
    return round(score, 3)
