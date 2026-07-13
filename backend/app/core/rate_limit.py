"""
Layer 8 — Rate limiting.

A minimal sliding-window limiter backed by an in-process dict. Fine for a
single backend instance; if you scale to multiple replicas, swap the store
for Redis (settings.USE_REDIS) using the same interface — INCR + EXPIRE.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

_WINDOW_SECONDS = 60
_hits: dict[str, deque] = defaultdict(deque)


def _key_for(request: Request, user_id: str | None) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{user_id or 'anon'}:{ip}"


async def rate_limit(request: Request, user_id: str | None = None) -> None:
    key = _key_for(request, user_id)
    now = time.monotonic()
    window = _hits[key]

    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()

    if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, slow down.",
        )

    window.append(now)
