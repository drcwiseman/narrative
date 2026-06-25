import json

from sqlalchemy.orm import Session

from app.models import DetectionRuleConfig
from app.services.analyzer import HARMFUL_PATTERNS, NEGATIVE_WORDS, TOPIC_KEYWORDS


def _default_rules() -> dict:
    return {
        "negative_words": sorted(NEGATIVE_WORDS),
        "harmful_patterns": list(HARMFUL_PATTERNS),
        "topic_keywords": {topic: sorted(words) for topic, words in TOPIC_KEYWORDS.items()},
        "default_harmful_threshold": 0.5,
        "platform_harmful_thresholds": {},
    }


def _safe_json_load(raw: str, fallback):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _ensure_row(db: Session) -> DetectionRuleConfig:
    row = db.query(DetectionRuleConfig).filter(DetectionRuleConfig.id == 1).first()
    if row:
        return row
    defaults = _default_rules()
    row = DetectionRuleConfig(
        id=1,
        negative_words_json=json.dumps(defaults["negative_words"]),
        harmful_patterns_json=json.dumps(defaults["harmful_patterns"]),
        topic_keywords_json=json.dumps(defaults["topic_keywords"]),
        default_harmful_threshold=defaults["default_harmful_threshold"],
        platform_harmful_thresholds_json=json.dumps(defaults["platform_harmful_thresholds"]),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_detection_rules(db: Session) -> dict:
    row = _ensure_row(db)
    return {
        "negative_words": _safe_json_load(row.negative_words_json, _default_rules()["negative_words"]),
        "harmful_patterns": _safe_json_load(row.harmful_patterns_json, _default_rules()["harmful_patterns"]),
        "topic_keywords": _safe_json_load(row.topic_keywords_json, _default_rules()["topic_keywords"]),
        "default_harmful_threshold": float(row.default_harmful_threshold or 0.5),
        "platform_harmful_thresholds": _safe_json_load(row.platform_harmful_thresholds_json, {}),
    }


def update_detection_rules(db: Session, payload: dict) -> dict:
    row = _ensure_row(db)
    row.negative_words_json = json.dumps(sorted({w.strip().lower() for w in payload["negative_words"] if w.strip()}))
    row.harmful_patterns_json = json.dumps([p.strip() for p in payload["harmful_patterns"] if p.strip()])
    row.topic_keywords_json = json.dumps(
        {
            topic.strip().lower(): sorted({w.strip().lower() for w in words if w.strip()})
            for topic, words in payload["topic_keywords"].items()
            if topic.strip()
        }
    )
    row.default_harmful_threshold = float(payload["default_harmful_threshold"])
    row.platform_harmful_thresholds_json = json.dumps(
        {k.strip().lower(): float(v) for k, v in payload["platform_harmful_thresholds"].items()}
    )
    db.commit()
    return get_detection_rules(db)
