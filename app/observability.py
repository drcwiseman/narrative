import time


METRICS = {
    "requests_total": 0,
    "requests_4xx": 0,
    "requests_5xx": 0,
    "mentions_ingested": 0,
    "alerts_dispatched": 0,
    "request_latency_ms_total": 0.0,
}


def track_request(status_code: int, latency_ms: float) -> None:
    METRICS["requests_total"] += 1
    if 400 <= status_code < 500:
        METRICS["requests_4xx"] += 1
    if status_code >= 500:
        METRICS["requests_5xx"] += 1
    METRICS["request_latency_ms_total"] += latency_ms


def average_latency_ms() -> float:
    total = METRICS["requests_total"]
    if total <= 0:
        return 0.0
    return round(METRICS["request_latency_ms_total"] / total, 3)


def metrics_snapshot() -> dict:
    return {
        **METRICS,
        "request_latency_ms_avg": average_latency_ms(),
        "timestamp_ms": int(time.time() * 1000),
    }
