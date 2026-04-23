"""
APIKeyMiddleware
Validates Bearer token on every request except exempt paths.
Attaches the resolved APIKey to request.state.api_key.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.services.keys import api_key_service


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exempt_paths: list[str] = None):
        super().__init__(app)
        self.exempt = set(exempt_paths or [])

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exempt:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Missing or malformed Authorization header. "
                               "Use: Authorization: Bearer zk_live_...",
                },
            )

        raw = auth.removeprefix("Bearer ").strip()
        key = api_key_service.validate(raw)
        if not key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Invalid or revoked API key.",
                },
            )

        request.state.api_key = key
        return await call_next(request)
