"""Test for the backend's one real endpoint.

Rule 13: test only what actually exists. Phase 2 implements exactly one
backend endpoint (GET /health, for environment verification per Rule 17) —
this test exercises that endpoint and nothing else. It does not assert
anything about business endpoints that don't exist yet.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


def test_health_endpoint_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "project-srt-backend"


def test_health_endpoint_reports_environment():
    response = client.get("/health")
    assert "environment" in response.json()
