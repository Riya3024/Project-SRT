# Project SRT — Module Ownership (Phase 1)

Maps every module defined in `docs/SYSTEM_DESIGN.md` to one of the six team tracks, and records the **final, authoritative phase allocation per member**. A module may have a primary owner and a supporting contributor; primary owner is listed first.

## Team Tracks and Final Phase Allocation (Authoritative)

- **M1 — AI/ML** — Phases: 8, 9, 10, 11, 12, 14, 14.5
- **M2 — Computer Vision** — Phases: 6, 7, 17, 18, 19
- **M3 — Video / Realtime / Edge** — Phases: 4, 5, 16, 20, 28
- **M4 — Backend / Data / Security** — Phases: 3, 13, 15, 21, 26
- **M5 — Frontend / Product / AI UX** — Phases: 22, 23, 24, 25
- **M6 — DevOps / QA / Production** — Phases: 2, 27, 29, 30, 31, 32

**Phase 1 (this document, and the architecture as a whole) is shared: ALL MEMBERS.** No later phase number listed above may begin before Phase 1 is accepted, since every later phase builds on the module boundaries and contract mappings defined here.

Track descriptions:
- **M1 — AI/ML:** model selection/integration, behavioral/anomaly/risk logic, evaluation.
- **M2 — CV:** detection, tracking, geometric/vision-pipeline engineering.
- **M3 — Video/Realtime/Edge:** ingestion, stream management, edge deployment concerns, camera health telemetry.
- **M4 — Backend/Data/Security:** FastAPI backend, data model, auth, tenancy, storage, API design.
- **M5 — Frontend/Product/AI UX:** React dashboard, investigation UX, AI search/summary UX.
- **M6 — DevOps/QA/Production:** deployment, observability infrastructure, testing infrastructure, production hardening.

## Ownership Table

Module-level ownership below is unchanged from the track descriptions above; it does not assign a specific phase number to each module — that finer-grained module→phase-number mapping is deferred to per-track phase planning (owned by each track lead) and is out of scope for the Phase 1 architecture deliverable.

| # | Module | Primary Owner | Supporting |
|---|---|---|---|
| 1 | Video Ingestion | M3 | — |
| 2 | Stream Management | M3 | M6 |
| 3 | Detection | M2 | M1 |
| 4 | Tracking | M2 | — |
| 5 | Activity Recognition | M1 | M2 |
| 6 | Behavioral Intelligence | M1 | — |
| 7 | Context Engine | M1 | M4 |
| 8 | Baseline | M1 | — |
| 9 | Anomaly Detection | M1 | — |
| 10 | Crowd Analytics | M1 | M2 |
| 11 | Zones | M2 | M4 |
| 12 | Vehicle / ANPR | M1 | M2 |
| 13 | Face Recognition | M1 | M4 (access control) |
| 14 | Re-ID | M1 | — |
| 15 | Camera Health | M3 | M6 |
| 16 | Risk Engine | M1 | M4 |
| 17 | Event | M4 | M1 |
| 18 | Incident Intelligence | M4 | M1 |
| 19 | Evidence | M4 | M6 (storage infra) |
| 20 | Alerts | M4 | M5 |
| 21 | Backend (FastAPI, Auth, API) | M4 | — |
| 22 | Frontend (React SaaS Dashboard) | M5 | — |
| 23 | AI Search | M1 | M5, M4 |
| 24 | AI Summaries | M1 | M5 |
| 25 | Deployment (edge/cloud) | M6 | M3 |
| 26 | Observability | M6 | all module owners (instrumentation) |

## Cross-Cutting Responsibilities (Not Owned by One Track Alone)

- **Contract stewardship:** the 23 frozen contracts are shared, cross-team assets. No single track owns them; any proposed change requires explicit project-lead authorization per Rule 1, regardless of which track raises the need.
- **Testing (Rule 8):** every module owner is responsible for their own module's tests; M6 owns the shared testing infrastructure/CI conventions.
- **Security (Rule 9, `ARCHITECTURE.md` §9):** M4 owns the security boundary design and secrets handling conventions; every track is responsible for not violating them (no hardcoded secrets in any module).
- **AI Evaluation (Rule 14):** M1 owns methodology (precision/recall/F1/latency/etc.) for every ML-bearing module (3–14, 16, 23, 24); results are documented per module, not only in aggregate.
- **Documentation of limitations (Rule 14):** each module owner documents known limitations of their module as part of that module's own implementation phase, not deferred indefinitely.

## Escalation Path

If a module's implementation appears to require a change to a frozen contract, the owning track stops (per Rule 1), documents the conflict in that module's phase report ("BLOCKED" section if implementation cannot proceed without the change, or a noted constraint if an implementation-level workaround is used), and raises it to the project lead. No track unilaterally modifies a contract.
