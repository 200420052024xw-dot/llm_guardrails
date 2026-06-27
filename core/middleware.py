import asyncio
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_settings

class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Origin check plus a small single-process abuse guard."""

    limits = {
        "/api/auth/login": 10,
        "/api/auth/register": 5,
        "/api/settings/model/test": 10,
    }

    def __init__(self, app):
        super().__init__(app)
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def dispatch(self, request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and not self._origin_allowed(origin, request.url.hostname):
                return JSONResponse({"detail": "请求来源无效"}, status_code=403)

        limit = self.limits.get(request.url.path)
        if request.url.path.endswith("/messages/stream"):
            limit = 30
        if limit:
            key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
            now = time.monotonic()
            async with self.lock:
                window = self.hits[key]
                while window and window[0] < now - 60:
                    window.popleft()
                if len(window) >= limit:
                    return JSONResponse({"detail": "请求过于频繁，请稍后再试"}, status_code=429)
                window.append(now)
        return await call_next(request)

    @staticmethod
    def _origin_allowed(origin: str, request_host: str | None) -> bool:
        configured = get_settings().frontend_origin.rstrip("/")
        origin_host = urlparse(origin).hostname
        return origin.rstrip("/") == configured or origin_host == request_host
