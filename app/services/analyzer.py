from __future__ import annotations

import re
from collections import Counter
from typing import Iterable


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
EMOTION_KEYWORDS = {
    "anger": {"angry", "rage", "betrayal", "outrage", "fight"},
    "fear": {"fear", "panic", "danger", "threat", "unsafe"},
    "hope": {"hope", "improve", "progress", "solution", "recovery"},
    "confusion": {"confused", "unclear", "rumor", "unsure", "unknown"},
    "trust": {"trust", "verified", "official", "credible", "evidence"},
}
TOPIC_KEYWORDS = {
    "elections": {"vote", "ballot", "election", "poll", "results"},
    "economy": {"jobs", "inflation", "tax", "business", "price"},
    "security": {"crime", "violence", "police", "security", "threat"},
    "health": {"hospital", "doctor", "vaccine", "health", "disease"},
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def score_sentiment(text: str, negative_words: Iterable[str] | None = None) -> float:
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    negative_set = {word.lower() for word in (negative_words or NEGATIVE_WORDS)}
    pos = sum(1 for token in tokens if token in POSITIVE_WORDS)
    neg = sum(1 for token in tokens if token in negative_set)
    score = (pos - neg) / max(len(tokens), 1)
    return round(max(-1.0, min(1.0, score * 4)), 3)


def extract_topic(text: str, topic_keywords: dict[str, set[str]] | None = None) -> str:
    tokens = set(_tokenize(text))
    scores: Counter[str] = Counter()
    mapping = topic_keywords or TOPIC_KEYWORDS
    for topic, keywords in mapping.items():
        scores[topic] += len(tokens.intersection(keywords))
    if not scores:
        return "general"
    topic, score = scores.most_common(1)[0]
    return topic if score > 0 else "general"


def harmful_claim_score(text: str, harmful_patterns: Iterable[str] | None = None) -> float:
    lowered = text.lower()
    patterns = list(harmful_patterns or HARMFUL_PATTERNS)
    hits = sum(1 for pattern in patterns if re.search(pattern, lowered))
    score = min(1.0, hits / max(len(patterns) / 3, 1))
    if "http" in lowered and ("fake" in lowered or "rigged" in lowered):
        score = min(1.0, score + 0.2)
    return round(score, 3)


def emotion_scores(text: str) -> dict[str, float]:
    tokens = _tokenize(text)
    if not tokens:
        return {"anger": 0.0, "fear": 0.0, "hope": 0.0, "confusion": 0.0, "trust": 0.0}
    token_count = max(len(tokens), 1)
    scores = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        hits = sum(1 for token in tokens if token in keywords)
        scores[emotion] = round(min(1.0, hits / token_count * 4), 3)
    return scores


def extract_claim_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for sentence in re.split(r"[.!?]+", text):
        line = sentence.strip()
        if len(line) < 20:
            continue
        lowered = line.lower()
        if any(word in lowered for word in ["will", "is", "are", "must", "caused", "stolen", "rigged", "fake"]):
            candidates.append(line)
    return candidates[:3]
