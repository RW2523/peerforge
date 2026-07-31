"""PeerForge API entry point"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routes import (
    health, agents, debates, turns, setup, summary, events, openrouter,
    personas, materials, memory, preflight, embeddings,
    workspace_settings, presence, websocket, knowledge, ai_assist,
    participants, autonomous, documents, action_items
)
from .routes.literature import router as literature_router
from .routes.web_search import router as web_search_router


app = FastAPI(
    title="PeerForge API",
    description="AI-Powered Academic Peer Review Platform",
    version="2.0.0"
)

PLACEHOLDER_JWT_SECRET = "your-jwt-secret-here"

if settings.require_auth and settings.supabase_jwt_secret == PLACEHOLDER_JWT_SECRET:
    raise RuntimeError(
        "REQUIRE_AUTH is enabled but SUPABASE_JWT_SECRET is still the placeholder. "
        "Any attacker could mint a valid token — set a real secret before serving traffic."
    )

# CORS middleware
_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
_wildcard = "*" in _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Starlette answers a wildcard by echoing the caller's Origin; combined with
    # credentials that lets any site make authenticated cross-origin calls.
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*", "X-OpenRouter-Key"],
    expose_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(agents.router, tags=["agents"])
app.include_router(debates.router, tags=["debates"])
app.include_router(turns.router, tags=["turns"])
app.include_router(setup.router, tags=["setup"])
app.include_router(summary.router, tags=["summary"])
app.include_router(events.router, tags=["events"])
app.include_router(openrouter.router, tags=["openrouter"])
app.include_router(personas.router, tags=["personas"])
app.include_router(materials.router, tags=["materials"])
app.include_router(memory.router, tags=["memory"])
app.include_router(preflight.router, tags=["preflight"])
app.include_router(embeddings.router, tags=["embeddings"])
app.include_router(workspace_settings.router, tags=["workspace-settings"])
app.include_router(presence.router, tags=["presence"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(knowledge.router, tags=["knowledge"])
app.include_router(ai_assist.router, tags=["ai-assist"])
app.include_router(participants.router, tags=["participants"])
app.include_router(autonomous.router, tags=["autonomous"])
app.include_router(documents.router, tags=["documents"])
app.include_router(action_items.router, tags=["action-items"])
app.include_router(literature_router, tags=["literature"])
app.include_router(web_search_router, tags=["web-search"])

from .routes.defense import router as defense_router
app.include_router(defense_router, tags=["defense"])

from .routes.assessment import router as assessment_router
app.include_router(assessment_router, tags=["assessment"])

from .routes.user_settings import router as user_settings_router
app.include_router(user_settings_router, tags=["user-settings"])

from .routes.me import router as me_router
app.include_router(me_router, tags=["me"])

from .routes.organizations import router as organizations_router
app.include_router(organizations_router, tags=["organizations"])

from .routes.conversational_setup import router as conversational_setup_router
app.include_router(conversational_setup_router, tags=["conversational-setup"])


# ── Account key resolution ───────────────────────────────────────────────────
# If a request needs an OpenRouter key but the browser did not send one
# (X-OpenRouter-Key header), fall back to the authenticated user's stored,
# encrypted key. Precedence: request header → account key → server default.
def _resolve_request_user_id(request) -> str:
    from .config import settings as _settings
    if not _settings.require_auth:
        from .auth import DEV_USER_ID
        return DEV_USER_ID
    auth_header = request.headers.get("authorization")
    if not auth_header:
        return ""
    try:
        from .auth import decode_jwt
        payload = decode_jwt(auth_header)
        return str(payload.get("sub") or "")
    except Exception:
        return ""


@app.middleware("http")
async def inject_account_openrouter_key(request, call_next):
    try:
        if not request.headers.get("x-openrouter-key"):
            user_id = _resolve_request_user_id(request)
            if user_id:
                from .routes.user_settings import get_cached_openrouter_key
                try:
                    key = get_cached_openrouter_key(user_id)
                except Exception:
                    key = None
                if key:
                    request.scope["headers"] = list(request.scope["headers"]) + [
                        (b"x-openrouter-key", key.encode())
                    ]
    except Exception:
        # Key injection is best-effort — never block the request on it.
        pass
    return await call_next(request)

# Document WebSocket endpoint
from .websocket.document_hub import handle_document_websocket

@app.websocket("/ws/document/{document_id}")
async def websocket_document_endpoint(websocket: WebSocket, document_id: str):
    """WebSocket endpoint for document collaboration"""
    await handle_document_websocket(websocket, document_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug
    )
