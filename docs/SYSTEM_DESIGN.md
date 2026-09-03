# Project SRT — System Design & Module Boundaries (Phase 1)

Companion to `docs/ARCHITECTURE.md`. This document defines the boundary, responsibility, inputs/outputs, and contract usage of every module. It does **not** implement any module (Rule 15) and does **not** define contract contents (Rule 1) — only which frozen contract each module produces or consumes.

Legend for "Status": all modules are `[ ] Not started (Phase 1 = interface/boundary definition only)` unless stated otherwise.

---

## 1. Video Ingestion — `services/ingestion/`

- **Responsibility:** Connect to CCTV/RTSP/MP4/webcam sources, normalize into a stable internal frame stream (resolution/fps handling), and hand frames to Detection. Owns reconnect/backoff logic for flaky streams.
- **Inputs:** Camera/stream configuration (URL, credentials via env/secrets, protocol).
- **Outputs:** Internal frame stream (not contract-bound — frames are not persisted as JSON); stream state events feeding Stream Management.
- **Contracts touched:** none directly produced; supplies data that Stream Management turns into `camera_health.schema.json`.
- **Degradation:** on source failure, retries with backoff and reports degraded/offline state via Stream Management rather than crashing the pipeline.
- **Owning team:** M3 (Video/Realtime/Edge).

## 2. Stream Management — `services/stream_manager/`

- **Responsibility:** Track per-camera stream lifecycle (connect/reconnect/disconnect), frame-rate/resolution negotiation, buffering strategy, and health telemetry.
- **Inputs:** Ingestion stream state.
- **Outputs:** `camera_health.schema.json`.
- **Contracts touched:** produces `camera_health.schema.json`.
- **Owning team:** M3.

## 3. Detection — `services/detection/`

- **Responsibility:** Run a pretrained object detector per frame (people, vehicles, and other relevant classes for border surveillance). Pluggable provider interface so the underlying pretrained model can be swapped (Rule 4).
- **Inputs:** Frames from Ingestion.
- **Outputs:** `detection.schema.json` — one message per `camera_id`+`frame_id`+`timestamp`, containing a `detections[]` array; each item has its own `detection_id`, `class`, `confidence` (0–1), `bbox`.
- **Contracts touched:** produces `detection.schema.json`; produces/updates `model_metadata.schema.json` for the active detector.
- **Degradation:** CPU fallback path when GPU unavailable/overloaded; documented expected latency delta (Rule 5).
- **Owning team:** M2 (CV) with M1 (AI/ML) for model selection/evaluation.

## 4. Tracking — `services/tracking/`

- **Responsibility:** Associate per-frame detections into persistent tracks across time within a single camera view, using a pretrained/classical tracking algorithm.
- **Inputs:** `detection.schema.json`.
- **Outputs:** `tracking.schema.json` — one message per `camera_id`+`timestamp`, containing a `tracks[]` array; each item has `track_id`, `class`, `confidence`, `bbox`, `centroid`, plus optional `velocity`/`acceleration`/`direction`/`track_age`/`tracking_confidence`.
- **Contracts touched:** produces `tracking.schema.json`; produces/updates `model_metadata.schema.json` where the tracker is model-based.
- **Owning team:** M2 (CV).

## 5. Activity Recognition — `services/activity_recognition/`

- **Responsibility:** Classify short-horizon actions/activities from track history (e.g., walking, running, loitering, climbing) using pretrained or lightweight temporal models.
- **Inputs:** `tracking.schema.json`.
- **Outputs:** `activity.schema.json`.
- **Contracts touched:** produces `activity.schema.json`.
- **Owning team:** M1 (AI/ML) with M2 (CV) for the feature/track interface.

## 6. Behavioral Intelligence — `services/behavior_intelligence/`

- **Responsibility:** Aggregate activities and track patterns over a longer temporal window into structured behavior observations (e.g., repeated boundary approach, group formation dynamics).
- **Inputs:** `activity.schema.json`, `tracking.schema.json`.
- **Outputs:** `behavior_observation.schema.json`.
- **Contracts touched:** produces `behavior_observation.schema.json`.
- **Owning team:** M1 (AI/ML).

## 7. Context Engine — `services/context/`

- **Responsibility:** Attach situational context to observations — camera/zone metadata, time-of-day/lighting, site-specific rules (e.g., restricted zone, expected traffic pattern), weather/visibility if available.
- **Inputs:** Camera/zone configuration, time, site metadata.
- **Outputs:** `context.schema.json`.
- **Contracts touched:** produces `context.schema.json`; consumed by nearly every downstream analytic stage.
- **Owning team:** M1 (AI/ML) with M4 (Backend/Data) for configuration storage.

## 8. Baseline (Normal Behavior) — `services/baseline/`

- **Responsibility:** Learn/maintain a statistical or model-based baseline of "normal" behavior per camera/zone/context, updated over time, used as the reference anomaly detection compares against.
- **Inputs:** Historical `behavior_observation.schema.json`, `context.schema.json`.
- **Outputs:** `baseline.schema.json`.
- **Contracts touched:** produces `baseline.schema.json`.
- **Technique direction:** classical statistical baselining preferred first (Rule 4); more complex modeling only if justified and documented.
- **Owning team:** M1 (AI/ML).

## 9. Anomaly Detection — `services/anomaly_detection/`

- **Responsibility:** Compare current `behavior_observation` + `context` against `baseline` to flag deviations, with confidence scores — never definitive claims (Rule 6).
- **Inputs:** `behavior_observation.schema.json`, `baseline.schema.json`, `context.schema.json`.
- **Outputs:** `anomaly.schema.json`.
- **Contracts touched:** produces `anomaly.schema.json`; produces/updates `model_metadata.schema.json` if model-based.
- **Evaluation:** precision/recall/F1/false-positive-rate tracked per Rule 14 once implemented.
- **Owning team:** M1 (AI/ML).

## 10. Crowd Analytics — `services/crowd_analytics/`

- **Responsibility:** Density/count estimation and crowd-level dynamics (formation, dispersal, flow direction) per camera/zone.
- **Inputs:** `tracking.schema.json`, `context.schema.json`.
- **Outputs:** `crowd.schema.json`.
- **Contracts touched:** produces `crowd.schema.json`.
- **Owning team:** M1 (AI/ML) with M2 (CV).

## 11. Zones — `services/zones/`

- **Responsibility:** Geofenced zone definitions (restricted areas, boundary lines) and detection of zone-relevant events (entry, exit, dwell, line-crossing).
- **Inputs:** `tracking.schema.json`, zone geometry configuration.
- **Outputs:** `zone_event.schema.json`.
- **Contracts touched:** produces `zone_event.schema.json`.
- **Owning team:** M2 (CV) for geometry/tracking integration, M4 (Backend) for zone configuration storage.

## 12. Vehicle / ANPR — `services/vehicle_anpr/`

- **Responsibility:** Vehicle classification/attributes and automatic number-plate recognition using pretrained detection + OCR models.
- **Inputs:** `detection.schema.json`, `tracking.schema.json`.
- **Outputs:** `vehicle.schema.json`, `anpr.schema.json`.
- **Contracts touched:** produces `vehicle.schema.json` and `anpr.schema.json`; produces/updates `model_metadata.schema.json`.
- **Owning team:** M1/M2 jointly.

## 13. Face Recognition — `services/face_recognition/`

- **Responsibility:** Face detection/embedding and (where a watchlist exists) similarity matching — always exposed as a similarity score, never an identity assertion (Rule 6).
- **Inputs:** `detection.schema.json`.
- **Outputs:** `face.schema.json`.
- **Contracts touched:** produces `face.schema.json`; produces/updates `model_metadata.schema.json`.
- **Security note:** access-controlled and audited per `docs/ARCHITECTURE.md` §9 — treated as sensitive personal data.
- **Owning team:** M1 (AI/ML) with M4 (Backend/Security) for access control.

## 14. Re-Identification (Re-ID) — `services/reid/`

- **Responsibility:** Cross-camera association of the same tracked entity using appearance embeddings, to support incident reconstruction across the camera fleet.
- **Inputs:** `detection.schema.json`, `tracking.schema.json`.
- **Outputs:** `reid.schema.json`.
- **Contracts touched:** produces `reid.schema.json`.
- **Architectural note:** inherently a cross-camera/central-compute concern (see edge-cloud split in `ARCHITECTURE.md` §8).
- **Owning team:** M1 (AI/ML).

## 15. Camera Health — `services/camera_health/`

- **Responsibility:** System-facing (not just stream-facing) health of each camera integration — uptime, frame-rate stability, last-seen, degraded-mode flags.
- **Inputs:** Telemetry from Ingestion/Stream Management.
- **Outputs:** `camera_health.schema.json`.
- **Owning team:** M3 (Video/Realtime/Edge) with M6 (DevOps) for fleet-level surfacing.

## 16. Risk Engine — `services/risk_engine/`

- **Responsibility:** Combine anomaly, crowd, zone, vehicle/ANPR, face, and re-ID signals into a single risk assessment with explicit contributing evidence and confidence, never a bare "yes/no" verdict (Rule 6).
- **Inputs:** `anomaly.schema.json`, `crowd.schema.json`, `zone_event.schema.json`, `vehicle.schema.json`, `anpr.schema.json`, `face.schema.json`, `reid.schema.json`.
- **Outputs:** `risk.schema.json` — `risk_score` (0–100), `risk_level` enum (`NORMAL/LOW/MEDIUM/HIGH/CRITICAL`), `confidence`/`uncertainty` (0–1), `contributing_factors[]`, and an optional `suppressed`/`suppression_reason` pair for false-positive suppression. `event_id` is nullable — a risk record can exist independently of an event.
- **Verified relationship (Rule 2/3 — confirmed against the real contracts):** Risk and Event are co-produced, not strictly sequential. `event.schema.json` embeds its own nullable `anomaly_score`/`risk_score`/`risk_level` snapshot alongside `risk.schema.json`'s own nullable `event_id`. Implementation should treat Risk Engine + Event creation as one tightly-coupled stage: the Risk Engine computes risk continuously; crossing a threshold creates an Event that snapshots the risk state, and the Risk record is (optionally) linked back via `event_id`.
- **Owning team:** M1 (AI/ML) with M4 (Backend) for the rules/aggregation service shell.

## 17. Event — (produced within `services/risk_engine/` or a dedicated `services/event/` boundary, decided at implementation time)

- **Responsibility:** Convert a risk assessment crossing a threshold into a discrete, queryable "event" record. See the Risk Engine note above — Event is co-produced with, not strictly downstream of, Risk.
- **Inputs:** `risk.schema.json`.
- **Outputs:** `event.schema.json` — `event_id`, `event_type`, `confidence` (required), plus nullable `anomaly_score`/`risk_score`/`risk_level` snapshot, `track_ids[]`, `reasons[]`, and a `status` enum (`DETECTED/CONFIRMED/DISMISSED/ESCALATED`).
- **Owning team:** M4 (Backend/Data), informed by M1's risk thresholds.

## 18. Incident Intelligence — `services/incident_intelligence/`

- **Responsibility:** Aggregate related events (same entity, same zone, same time window) into an incident, track incident lifecycle/state (open, under review, resolved), and support operator workflows.
- **Inputs:** `event.schema.json` (aggregated).
- **Outputs:** `incident.schema.json`.
- **Owning team:** M4 (Backend/Data) with M1 for correlation logic.

## 19. Evidence — `services/evidence/`

- **Responsibility:** Bundle the media/data (clips, snapshots, contributing contract records) that substantiate an incident, and manage evidence lifecycle (see retention, `ARCHITECTURE.md` §13).
- **Inputs:** `incident.schema.json`, `event.schema.json`, raw media references.
- **Outputs:** `evidence.schema.json`.
- **Owning team:** M4 (Backend/Data) for storage/lifecycle, M6 (DevOps) for object storage infrastructure.

## 20. Alerts — `services/alerts/`

- **Responsibility:** Notify operators of new/escalating incidents through the appropriate channel (dashboard, and future push/mobile per `ARCHITECTURE.md` §6).
- **Inputs:** `incident.schema.json`, `risk.schema.json`.
- **Outputs:** `alert.schema.json`.
- **Owning team:** M4 (Backend) with M5 (Frontend) for delivery/UX.

## 21. Backend — `backend/`

- **Responsibility:** FastAPI application exposing the API-first surface (§5 of `ARCHITECTURE.md`): auth, tenancy enforcement, CRUD/query over events/incidents/evidence/alerts/cameras, AI search, AI summaries, and the `api_response.schema.json` envelope for all responses.
- **Inputs:** All downstream contract data (events, incidents, evidence, alerts, camera health, model metadata) plus operator actions.
- **Outputs:** `api_response.schema.json`-wrapped REST/WebSocket responses; consumes/produces `operator_feedback.schema.json` when operators annotate or correct system output.
- **Verified constraint:** `api_response.schema.json` sets `additionalProperties: false` at the top level and inside `error`. Only `success`, `request_id`, `timestamp`, `data`, `error`, `meta` are permitted — no ad-hoc extra fields; anything else belongs inside `data` or `meta`.
- **Verified constraint (tenant enforcement):** since `tenant_id` is not present on most contracts (see `ARCHITECTURE.md` §7), the backend is responsible for enforcing tenant scoping by joining through each record's `camera_id` to a backend-owned camera→tenant mapping, except for `incident.schema.json`, which carries an optional `tenant_id` directly.
- **Owning team:** M4 (Backend/Data/Security).

## 22. Frontend — `frontend/`

- **Responsibility:** React SaaS dashboard: live camera/incident views, investigation workflows, AI Search UI, AI Summary UI, alert inbox — all driven by the backend API, no independent business logic.
- **Inputs:** Backend API (`api_response.schema.json`-wrapped payloads).
- **Outputs:** Operator actions back to backend (which become `operator_feedback.schema.json` where relevant).
- **Owning team:** M5 (Frontend/Product/AI UX).

## 23. Authentication — `auth/`

- **Responsibility:** Identity, session/token issuance, RBAC enforcement, tenant binding of users. Cross-cutting: enforced at the API boundary for every route (`ARCHITECTURE.md` §9).
- **Owning team:** M4 (Backend/Data/Security).

## 24. AI Search — `services/ai_search/`

- **Responsibility:** Natural-language / structured query over events, incidents, and evidence (e.g., "show unauthorized zone entries near Camera 4 last night"), translating to queries over the underlying contract-conformant data.
- **Inputs:** Operator query (via backend), indexed event/incident/evidence data.
- **Outputs:** Ranked/query results, delivered via `api_response.schema.json`.
- **Owning team:** M1 (AI/ML) with M5 (Frontend/AI UX) for query UX and M4 for the data access layer.

## 25. AI Summaries — `services/ai_summary/`

- **Responsibility:** Generate human-readable summaries of incidents/shifts/time windows from underlying structured records, using probabilistic language consistent with Rule 6 (no definitive claims of intent/guilt).
- **Inputs:** `incident.schema.json`, `event.schema.json`, `evidence.schema.json`.
- **Outputs:** Summary text, delivered via `api_response.schema.json`.
- **Owning team:** M1 (AI/ML) with M5 (Frontend/AI UX).

## 26. Deployment — `deployment/edge/`, `deployment/cloud/`

- **Responsibility:** Deployment topology for edge-capable vs. cloud-preferred stages (`ARCHITECTURE.md` §8), packaging, and environment configuration. No deployment automation is implemented in Phase 1 — directories exist as placeholders for the phase that implements them.
- **Owning team:** M6 (DevOps/QA/Production).

## 27. Observability — `observability/`

- **Responsibility:** Cross-cutting logging/metrics/health-check conventions (`ARCHITECTURE.md` §12), shared across all services. Placeholder in Phase 1.
- **Owning team:** M6 (DevOps/QA/Production), with every module owner responsible for instrumenting their own service against the shared convention.

---

## Contract Coverage Check

All 23 frozen contracts are referenced by at least one module above, and all 23 have now been verified against the actual uploaded `*.schema.json` files (valid JSON, `draft/2020-12`, field/enum names confirmed by direct inspection — not assumed):

`common`(shared vocabulary, not `$ref`-composed into any contract) · `detection`(3) · `tracking`(4) · `activity`(5) · `behavior_observation`(6) · `context`(7) · `baseline`(8) · `anomaly`(9) · `crowd`(10) · `zone_event`(11) · `risk`(16) · `event`(17) · `incident`(18) · `evidence`(19) · `alert`(20) · `vehicle`(12) · `anpr`(12) · `face`(13) · `reid`(14) · `camera_health`(2/15) · `operator_feedback`(21) · `api_response`(21) · `model_metadata`(3/4/6/9/12/13)

No contract is unused; no module invents a contract outside this list (Rule 1). No contract field, enum, or requirement was altered to make this coverage check pass — the module descriptions above were corrected to match the contracts, not the reverse.
