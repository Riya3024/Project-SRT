"""Project SRT backend — Phase 2 environment-verification app.

IMPORTANT (Rule 3 / Rule 11): this file intentionally contains ONLY a health
check endpoint. It exists to prove the Python/FastAPI development environment
is reproducible and startable (Rule 20), not to implement any business API.

Real endpoints (auth, cameras, events, incidents, evidence, alerts, AI
search/summary, etc.) are implemented starting Phase 3 (M4) and onward, each
wrapped in the frozen api_response.schema.json envelope. That wrapping is
deliberately NOT done for this /health endpoint, because designing the
mapping from internal health state to the contract envelope is itself
business logic reserved for a later phase — this endpoint returns a plain,
minimal JSON body.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="Project SRT Backend (Phase 2 — environment scaffold)",
    description="No business endpoints implemented yet. See docs/DEVELOPMENT_SETUP.md.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    """Liveness check only. Not a business endpoint."""
    return {
        "status": "ok",
        "service": "project-srt-backend",
        "environment": settings.environment,
    }
