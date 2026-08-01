from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.middlewares import LoggingMiddleware, RequestIDMiddleware
from app.core.protection import RequestProtectionMiddleware, SecurityHeadersMiddleware
from app.modules.ai.mcp import init_mcp


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "Multi-tenant AI assistant API. "
        "All routes are served under the `/api/v1` prefix.\n\n"
        "## Authentication\n\n"
        "1. Register a user with `POST /auth/register` and verify the email. "
        "2. Login with `POST /auth/login` to obtain a JWT bearer token. "
        "3. Send the token in the `Authorization` header as `Bearer <token>`.\n\n"
        "Protected routes return `401` when the token is missing or invalid, "
        "and `403` when the account is deactivated.\n\n"
        "## AI Chat\n\n"
        "The `/ai` module manages chat sessions, message history, system prompts, "
        "and context summaries. Sessions expire automatically after 24 hours.\n\n"
        "## Client Integration\n\n"
        "This API is consumed by humans through a web frontend and by AI agents "
        "through an MCP server that maps each route to a tool. Routes marked as "
        "AI-protected are intentionally forbidden to AI agents."
    ),
    openapi_tags=[
        {
            "name": "Health",
            "description": "Service health and readiness probes.",
        },
        {
            "name": "Authentication",
            "description": "User registration, login, password recovery, and profile.",
        },
        {
            "name": "AI Chat",
            "description": "Create and manage AI chat sessions, send messages, "
            "configure system prompts, and retrieve context summaries.",
        },
        {
            "name": "WhatsApp",
            "description": "Provider-agnostic WhatsApp integrations, contacts, "
            "conversations, and messages.",
        },
        {
            "name": "WhatsApp Webhooks",
            "description": "Public Meta WhatsApp Cloud API webhook verification "
            "and event reception.",
        },
    ],
    lifespan=lifespan,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(RequestProtectionMiddleware)

app.add_middleware(RequestIDMiddleware)

app.add_middleware(LoggingMiddleware)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)


app.include_router(api_router, prefix=settings.API_V1_PREFIX)

init_mcp(app)
