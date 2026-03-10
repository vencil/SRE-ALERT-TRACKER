"""Auth middleware — extracts user identity from request headers or defaults.

AUTH_MODE=oauth2-proxy: reads X-Forwarded-User / X-Forwarded-Email set by oauth2-proxy.
AUTH_MODE=none: injects a default "dev-user" for local/lab development.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import AuthMode, settings

logger = logging.getLogger("alert-tracker.auth")


class AuthMiddleware(BaseHTTPMiddleware):
    """Inject request.state.user based on AUTH_MODE."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip auth for health check and OpenAPI docs
        if request.url.path in ("/api/health", "/docs", "/openapi.json", "/redoc"):
            request.state.user = "anonymous"
            return await call_next(request)

        if settings.auth_mode == AuthMode.OAUTH2_PROXY:
            user = request.headers.get("X-Forwarded-User", "").strip()
            email = request.headers.get("X-Forwarded-Email", "").strip()

            if not user and not email:
                logger.warning("oauth2-proxy mode: missing user headers on %s", request.url.path)
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required — no X-Forwarded-User header"},
                )

            request.state.user = user or email
            request.state.email = email or ""
        else:
            # AUTH_MODE=none — lab/dev mode
            request.state.user = "dev-user"
            request.state.email = ""

        return await call_next(request)
