import json
import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.observability import track_request


RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    started = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - started) * 1000
    track_request(response.status_code, latency_ms)
    response.headers["X-Request-Id"] = request_id
    print(
        json.dumps(
            {
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 3),
            }
        )
    )
    return response


async def basic_rate_limit_middleware(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{request.url.path}"
    now = time.time()
    window = RATE_BUCKETS[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    window.append(now)
    return await call_next(request)
