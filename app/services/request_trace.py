from __future__ import annotations

from dataclasses import asdict, dataclass

from fastapi import Request


@dataclass
class IngestTraceContext:
    source_ip: str
    forwarded_for: str = ""
    user_agent: str = ""
    ingest_channel: str = "unknown"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> IngestTraceContext | None:
        if not data:
            return None
        return cls(
            source_ip=str(data.get("source_ip") or "unknown"),
            forwarded_for=str(data.get("forwarded_for") or "")[:1024],
            user_agent=str(data.get("user_agent") or "")[:512],
            ingest_channel=str(data.get("ingest_channel") or "unknown"),
        )


def extract_client_ip(request: Request, *, ingest_channel: str = "unknown") -> IngestTraceContext:
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    vercel_ip = (request.headers.get("x-vercel-forwarded-for") or "").strip()

    if forwarded:
        source_ip = forwarded.split(",")[0].strip()
    elif vercel_ip:
        source_ip = vercel_ip.split(",")[0].strip()
    elif real_ip:
        source_ip = real_ip
    elif request.client and request.client.host:
        source_ip = request.client.host
    else:
        source_ip = "unknown"

    return IngestTraceContext(
        source_ip=source_ip[:64],
        forwarded_for=forwarded or vercel_ip,
        user_agent=(request.headers.get("user-agent") or "")[:512],
        ingest_channel=ingest_channel,
    )
