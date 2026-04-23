"""
RateLimitMiddleware
Simple in-memory sliding-window rate limiter per API key.
Production: swap _store for Redis with EXPIRE.

Limits:
  live keys: 100 req/min
  test keys: 20  req/min
"""

import time
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

LIMITS = {"live": 100, "test": 20}
WINDOW = 60  # seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._windows: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        key = getattr(getattr(request, "state", None), "api_key", None)
        if key is None:
            return await call_next(request)

        bucket = key.key_hash[:16]
        limit  = LIMITS.get(key.env, 20)
        window = self._windows[bucket]
        now    = time.monotonic()

        # Evict timestamps outside the window
        while window and window[0] < now - WINDOW:
            window.popleft()

        if len(window) >= limit:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                content={
                    "error":   "rate_limit_exceeded",
                    "message": f"Limit: {limit} requests/min for {key.env} keys.",
                    "retry_after_seconds": 60,
                },
            )

        window.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(limit - len(window))
        response.headers["X-RateLimit-Reset"]     = str(int(now + WINDOW))
        return response
