# Project SRT (Smart Recognition and Tracking)

AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV infrastructure — SIH26187.

**Current phase:** Phase 1 — System Architecture (documentation and repository skeleton only; no AI/CV/backend/frontend code implemented).

## Start Here

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — overall system architecture, data flow, API-first design, SaaS/multi-tenant model, edge-cloud split, model versioning, evidence storage, observability, security, retention, and MVP-vs-production-vs-SaaS-vs-Android distinctions.
- [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) — module-by-module boundaries, responsibilities, inputs/outputs, and contract mapping.
- [`docs/MODULE_OWNERSHIP.md`](docs/MODULE_OWNERSHIP.md) — mapping of every module to the M1–M6 team tracks and the final phase allocation.
- [`docs/DEVELOPMENT_SETUP.md`](docs/DEVELOPMENT_SETUP.md) — **start here to get a working dev environment**: prerequisites, backend/frontend setup, environment variables, contract validation, tests, lint/format, GPU verification, troubleshooting (Phase 2).

## Repository Layout

```
project-srt/
├── docs/                     Architecture, design, module ownership, and dev-setup docs
├── contracts/                The 23 frozen Contract v1.0 schema files (verified, unmodified)
├── backend/                  FastAPI backend — Phase 2: only a /health endpoint exists (env scaffold)
│   ├── app/
│   │   ├── main.py           FastAPI app + /health endpoint
│   │   └── config.py         Environment-driven settings
│   └── requirements.txt      Backend-specific runtime dependencies
├── frontend/                 React + TypeScript SaaS dashboard — Phase 2: placeholder scaffold only
│   ├── src/                  Minimal App/main entry, no dashboard features yet
│   └── package.json
├── services/                 One directory per pipeline/domain module (still empty placeholders)
│   ├── ingestion/  stream_manager/  detection/  tracking/  activity_recognition/
│   ├── behavior_intelligence/  context/  baseline/  anomaly_detection/  crowd_analytics/
│   ├── zones/  risk_engine/  incident_intelligence/  evidence/  vehicle_anpr/
│   ├── face_recognition/  reid/  camera_health/  alerts/  ai_search/  ai_summary/
├── auth/                     Authentication/authorization — not implemented yet
├── deployment/
│   ├── edge/                 Edge deployment topology — not implemented yet
│   └── cloud/                Cloud deployment topology — not implemented yet
├── observability/            Shared logging/metrics/health-check conventions — not implemented yet
├── scripts/                  validate_contracts.py, check_gpu.py — repo-wide dev tooling
├── tests/                    contracts/ and backend/ tests (only what actually exists — Rule 13)
├── requirements.txt          Shared Python runtime deps (jsonschema, python-dotenv)
├── requirements-dev.txt      Shared Python dev deps (pytest, black, ruff, mypy, httpx)
├── pyproject.toml            Tool configuration (black, ruff, mypy, pytest)
├── .env.example               Environment variable template (placeholders only)
└── .gitignore
```

## Important Constraints Carried Forward From the Global Rules

- The 23 contracts are **Contract v1.0 and FROZEN**. This repository does not contain them yet (none existed at the time Phase 1 began) and Phase 1 does not create them — see `contracts/README.md`. When they are added, they are the source of truth; documentation must be reconciled to them, not vice versa.
- No AI/CV/backend/frontend implementation exists yet — this phase is architecture and documentation only.
- No Android application exists or is planned for implementation until an explicit future phase assigns it.
- No secrets are, or should ever be, committed to this repository.

## Phase Log

- **Phase 1 (all members):** System architecture and documentation.
- **Phase 2 (M6):** Repository and development-environment setup — see `docs/DEVELOPMENT_SETUP.md` and this phase's `PHASE 2 STATUS` report for the full record (files created, tests run, limitations, next-phase notes).
