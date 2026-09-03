# Project SRT — Architecture (Phase 1)

**Project:** Smart Recognition and Tracking (SRT)
**Reference:** SIH26187 — AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV infrastructure
**Phase:** 1 — System Architecture
**Status:** Foundational architecture only. No AI/CV modules implemented in this phase.
**Contracts:** All 23 contracts are Contract v1.0 and FROZEN. This document does not define or modify contract schemas — it maps modules to contracts by name and purpose only.

> **Repository state at time of writing:** The 23 real Contract v1.0 `*.schema.json` files have been supplied and inspected (see `contracts/README.md` for the inspection notes) and are now present, verbatim and unmodified, under `contracts/`. This document has been reconciled against their actual field names, required fields, and enums. Where reconciliation surfaced a discrepancy with an earlier draft of this document, the contract won and the document was corrected — never the reverse.

---

## 1. System Purpose

SRT ingests video from existing CCTV / RTSP / MP4 / webcam sources and produces a pipeline of increasingly higher-level intelligence: detections → tracks → activities → behavior → context-aware baselines → anomalies → domain analytics (crowd, zone, vehicle, face, re-identification) → risk scoring → events → incidents → evidence → alerts. All of this is exposed through an API-first FastAPI backend, consumed by a React SaaS dashboard, and designed so a future mobile client can be added without backend rework.

The system is explicitly **decision-support**, not an autonomous accuser. See Rule 6 (AI Uncertainty) — outputs are probabilistic and evidentiary, never definitive claims of criminal intent, identity, or guilt.

## 2. High-Level Architecture

```
                          ┌─────────────────────────────────────────────┐
                          │           EDGE / INGESTION LAYER             │
                          │  CCTV / RTSP / MP4 / Webcam                  │
                          │        ↓                                     │
                          │  Video Ingestion  ──▶  Stream Management     │
                          │        ↓                                     │
                          │  Detection  ──▶  Tracking                    │
                          └───────────────────┬───────────────────────────┘
                                              │ (detection.schema, tracking.schema)
                          ┌───────────────────▼───────────────────────────┐
                          │        TEMPORAL / BEHAVIORAL INTELLIGENCE     │
                          │  Activity Recognition                        │
                          │        ↓                                     │
                          │  Behavior Observation                        │
                          │        ↓                                     │
                          │  Context Engine  ──▶  Baseline (Normal Behavior)│
                          └───────────────────┬───────────────────────────┘
                                              │ (behavior_observation, context, baseline)
                          ┌───────────────────▼───────────────────────────┐
                          │           ML ANOMALY + DOMAIN ANALYTICS       │
                          │  Anomaly Detection                           │
                          │  Crowd Analytics │ Zone Events │ Vehicle/ANPR │
                          │  Face Recognition │ Re-ID │ Camera Health     │
                          └───────────────────┬───────────────────────────┘
                                              │ (anomaly, crowd, zone_event,
                                              │  vehicle, anpr, face, reid,
                                              │  camera_health)
                          ┌───────────────────▼───────────────────────────┐
                          │              DECISION LAYER                   │
                          │  Risk Engine ──▶ Event ──▶ Incident Intelligence│
                          │        ↓                                     │
                          │  Evidence  ──▶  Alerts                       │
                          └───────────────────┬───────────────────────────┘
                                              │ (risk, event, incident,
                                              │  evidence, alert)
                          ┌───────────────────▼───────────────────────────┐
                          │            BACKEND (FastAPI, API-first)       │
                          │  Auth │ Tenancy │ Query │ AI Search │ AI Summary│
                          │  api_response.schema wraps all responses      │
                          └───────────────────┬───────────────────────────┘
                                              │ REST / WebSocket / (future gRPC)
                          ┌───────────────────▼───────────────────────────┐
                          │        FRONTEND — React SaaS Dashboard        │
                          │  Investigation UI │ AI Search UI │ Summaries  │
                          └───────────────────┬───────────────────────────┘
                                              │ same API surface
                          ┌───────────────────▼───────────────────────────┐
                          │   FUTURE: Mobile client (API-consumer only)   │
                          └───────────────────────────────────────────────┘
```

This mirrors the pipeline given in the global rules exactly; no stage has been added, removed, or reordered.

## 3. Architectural Principles

1. **Contract-driven boundaries.** Every inter-module data exchange is expressed as one of the 23 frozen schemas. A module never reaches into another module's internals — it only produces/consumes contract-conformant JSON.
2. **Pipeline stages are independently deployable services**, not function calls in one process. Phase 1 defines the boundaries; later phases decide the concrete transport (in-process call for the MVP demo, message bus for production — see §10).
3. **API-first.** The backend is the only supported way to reach the system's data and control surface. The React dashboard is a client of that API, not a privileged consumer. This is what makes a future Android client possible without new backend work (Rule 11).
4. **Multi-tenant from day one at the data-model level**, even though the SIH MVP may run single-tenant in practice (Rule 12, §8).
5. **Pretrained-first AI.** No stage in this architecture assumes training a model from scratch. Detection, tracking, pose, OCR/ANPR, face, and re-ID stages are designed as pluggable "model providers" behind a stable interface, so pretrained models can be swapped without touching the pipeline (Rule 4).
6. **Graceful degradation.** Every stage must define a documented fallback/degraded mode (e.g., detector unavailable → ingestion still records and flags camera_health; GPU unavailable → CPU fallback with reduced frame rate) (Rule 5).
7. **Uncertainty is a first-class citizen.** Every ML-derived output field structurally carries confidence/similarity/evidence, per Rule 6. This is enforced at the contract level (already true of the frozen contracts by their field names such as `confidence`, `similarity_score`, etc. — Phase 1 does not change this, only documents the expectation).
8. **Observability is not optional.** Every module exposes health/metrics/version metadata using `camera_health.schema.json` and `model_metadata.schema.json` conventions, plus structured logs (§12).
9. **Phase boundary discipline.** Phase 1 delivers architecture and documentation only. No detector, tracker, or ML code is implemented here (Rule 15).

## 4. Data Flow (Contract-Level)

| Stage | Produces | Consumes |
|---|---|---|
| Video Ingestion | raw frame stream (internal, not a contract — frames are not persisted as JSON) | camera/stream configuration |
| Stream Management | `camera_health.schema.json` | ingestion stream state |
| Detection | `detection.schema.json` | frames from ingestion |
| Tracking | `tracking.schema.json` | `detection.schema.json` |
| Activity Recognition | `activity.schema.json` | `tracking.schema.json` |
| Behavioral Intelligence | `behavior_observation.schema.json` | `activity.schema.json`, `tracking.schema.json` |
| Context Engine | `context.schema.json` | camera/zone metadata, time-of-day, site config |
| Baseline | `baseline.schema.json` | historical `behavior_observation.schema.json` + `context.schema.json` |
| Anomaly Detection | `anomaly.schema.json` | `behavior_observation.schema.json`, `baseline.schema.json`, `context.schema.json` |
| Crowd Analytics | `crowd.schema.json` | `tracking.schema.json`, `context.schema.json` |
| Zones | `zone_event.schema.json` | `tracking.schema.json`, zone geometry config |
| Vehicle/ANPR | `vehicle.schema.json`, `anpr.schema.json` | `detection.schema.json`, `tracking.schema.json` |
| Face Recognition | `face.schema.json` | `detection.schema.json` |
| Re-ID | `reid.schema.json` | `detection.schema.json`, `tracking.schema.json` |
| Camera Health | `camera_health.schema.json` | ingestion/stream telemetry |
| Risk Engine | `risk.schema.json` (co-produced with Event, see note below) | `anomaly`, `crowd`, `zone_event`, `vehicle`, `anpr`, `face`, `reid` |
| Event | `event.schema.json` (embeds a snapshot of `anomaly_score`/`risk_score`/`risk_level`) | `risk.schema.json` |
| Incident Intelligence | `incident.schema.json` | `event.schema.json` (aggregation over time/related events) |
| Evidence | `evidence.schema.json` | `incident.schema.json`, `event.schema.json`, raw media references |
| Alerts | `alert.schema.json` | `incident.schema.json`, `risk.schema.json` |
| Backend API | `api_response.schema.json` (envelope for all of the above) | all of the above, plus `operator_feedback.schema.json`, `model_metadata.schema.json` |
| Operator Feedback | `operator_feedback.schema.json` | operator actions in dashboard, fed back toward baseline/anomaly tuning |
| Model Metadata | `model_metadata.schema.json` | every model-bearing stage (detection, tracking, activity, anomaly, vehicle/anpr, face, reid) |
| `common.schema.json` | shared primitive types (ids, timestamps, geo, tenant, camera refs) | used by every contract above |

Full module-by-module detail (owners, responsibilities, tech direction) is in `docs/SYSTEM_DESIGN.md`. Team ownership mapping (M1–M6) is in `docs/MODULE_OWNERSHIP.md`.

**Verified structural notes from contract inspection (informational, contracts unmodified):**
- `detection.schema.json` and `tracking.schema.json` are **per-frame batch envelopes**: one message per `camera_id` + `timestamp`(/`frame_id`), containing an array (`detections[]` / `tracks[]`) where each item carries its own `confidence`. Downstream consumers (Activity Recognition, Behavioral Intelligence, Crowd Analytics, Zones, Vehicle/ANPR, Face, Re-ID) consume these batches, not single-object messages.
- **Risk and Event are co-produced, not strictly sequential.** `risk.schema.json.event_id` is nullable (a risk assessment can exist before, or without, an event), and `event.schema.json` carries its own nullable `anomaly_score`/`risk_score`/`risk_level` snapshot. In practice the Risk Engine computes risk continuously; when a threshold is crossed it creates (or is linked to) an Event that snapshots the risk state at that moment. Module code should treat Risk Engine and Event creation as one tightly-coupled stage, not two strictly ordered ones.
- `api_response.schema.json` sets `"additionalProperties": false` at the top level and inside `error`. The backend must not add ad-hoc top-level fields to a response — anything beyond `success`/`request_id`/`timestamp`/`data`/`error`/`meta` belongs inside `data` or `meta`.
- Score scales differ by contract and must not be confused: `confidence`, `similarity`, `correlation_confidence`, `uncertainty` are 0–1; `anomaly_score` and `risk_score` are 0–100.

## 5. API-First Architecture

- The FastAPI backend is the single integration point. All clients (React dashboard, future Android app, third-party integrations) talk to the same versioned REST/WebSocket surface.
- Every response is wrapped in `api_response.schema.json` for consistent success/error/pagination semantics.
- Internal pipeline stages (ingestion → ... → alerts) do **not** talk directly to the frontend. They write to a shared data/event layer; the backend reads from that layer and serves it.
- Authentication/authorization (see §9) is enforced at the API boundary, not duplicated per-client.
- Versioning: API routes are namespaced (`/api/v1/...`) from the start so that contract evolution (post v1.0, with explicit authorization) does not break existing clients.

## 6. Future Android Architecture (Not Implemented — Rule 11)

Android is explicitly out of scope for implementation in any phase unless a phase says otherwise. This section documents the *shape* the backend must preserve so Android can be added later with zero backend changes:

- **Same API, same contracts.** Android consumes the identical `/api/v1` surface and `api_response.schema.json` envelope as the web dashboard. No mobile-only endpoints.
- **AuthN/AuthZ must be token-based** (e.g., short-lived access token + refresh token), not session-cookie-only, so a native client can authenticate without a browser context.
- **Payload size discipline.** Endpoints that return evidence/media should return references (object storage URLs, see §11) rather than embedding large binary payloads, so mobile bandwidth stays bounded.
- **Push/alerting hook point.** `alert.schema.json`-based alerts should be deliverable through a notification-agnostic mechanism (e.g., an internal event that a future push-notification service subscribes to), rather than the alert pipeline assuming a specific transport.
- **Offline tolerance.** Mobile-facing read endpoints should be designed as idempotent, cacheable GETs where possible, anticipating intermittent connectivity — this is a design constraint on the API now, not mobile code.
- **No business logic duplication.** Anything Android will eventually need (risk thresholds, alert rules, incident state transitions) lives in the backend, never re-implemented client-side.

## 7. SaaS / Multi-Tenant Architecture

Hierarchy (Rule 12):

```
Organization (Tenant)
   └── Users (with roles)
         └── Cameras
               └── Events
                     └── Incidents
                           └── Evidence
                     └── Alerts
   └── Models / Configuration (per-tenant overrides of shared model defaults)
```

- **Tenant isolation, as actually encoded in Contract v1.0, is mostly indirect — not a `tenant_id` field on every record.** Contract inspection confirms `tenant_id` appears explicitly on only 2 of the 23 contracts: `common.schema.json` (a shared vocabulary definition that is not `$ref`-composed into any other contract) and `incident.schema.json` (a real, optional field). None of `detection`, `tracking`, `activity`, `behavior_observation`, `context`, `baseline`, `anomaly`, `crowd`, `zone_event`, `risk`, `event`, `evidence`, `alert`, `vehicle`, `anpr`, `face`, `reid`, `camera_health`, `operator_feedback`, `api_response`, or `model_metadata` carry a `tenant_id` field.
  Consequently, the backend must enforce tenant isolation **indirectly, via camera ownership**: every `camera_id` is registered to exactly one tenant in the backend's own data model (outside the frozen contracts, since cameras-to-tenant mapping is backend configuration, not pipeline output), and every query over camera-scoped contract data (detection, tracking, events, risk, alerts, etc.) is scoped by joining through `camera_id → tenant`. `incident.schema.json`'s own `tenant_id` field can be used directly once an incident is created, but should still be validated against the tenant(s) implied by its `camera_ids[]` to prevent drift.
  This is a real constraint on the backend implementation, not a documentation preference: no module should assume it can read `tenant_id` off a `detection`, `event`, `risk`, or `alert` record directly — it isn't there.
- **Compute isolation** is a deployment concern, not a Phase 1 concern: the SIH MVP may run shared compute for all cameras of one tenant; a later production phase may add per-tenant queueing/throttling. This document does not lock in a specific isolation strength beyond "no data leakage," per Rule 12.
- **Configuration and model overrides** (thresholds, zone geometry, baseline sensitivity) are tenant-scoped so one organization's tuning never affects another's.
- **Users/roles** (operator, analyst, admin, auditor) are tenant-scoped; a user belongs to exactly one tenant in the MVP design, with room to extend to multi-tenant users later if required.

## 8. Edge–Cloud Architecture

Given the hardware baseline (Rule 5: Windows/HP Omen, GTX 3050, 16GB RAM, 512GB SSD) and the border-surveillance use case (bandwidth-constrained CCTV sites), the architecture separates **edge-capable** stages from **cloud-preferred** stages:

| Layer | Runs at Edge (near camera) | Runs in Cloud/Central |
|---|---|---|
| Video Ingestion | ✅ required | — |
| Stream Management / Camera Health | ✅ required | mirrored for fleet view |
| Detection | ✅ preferred (reduces upstream bandwidth) | ✅ fallback if edge GPU unavailable |
| Tracking | ✅ preferred (needs low-latency access to detections) | possible if detection is centralized |
| Activity / Behavior / Context / Baseline / Anomaly | ⚠️ edge-capable for lightweight models; heavier models centralized | ✅ default for MVP |
| Crowd / Zone / Vehicle-ANPR / Face / Re-ID | ⚠️ edge-capable per-camera; cross-camera Re-ID needs central correlation | ✅ cross-camera correlation is inherently central |
| Risk Engine / Event / Incident / Evidence / Alerts | — | ✅ central (needs cross-camera, cross-time aggregation) |
| Backend API / Frontend / Auth | — | ✅ central |

Design rule: any stage marked edge-capable must be able to run with a **CPU-only fallback** and a reduced frame-rate/resolution profile, and must report degraded mode via `camera_health.schema.json`, per Rule 5 and Rule 6 (graceful degradation).

The SIH MVP demo is expected to run most/all stages on a single development machine (the stated hardware) for simplicity; the edge/cloud split above is the target production topology, not a Phase 1 requirement.

## 9. Security Boundaries

- **AuthN/AuthZ at the API boundary** only (§5); internal pipeline services are not directly internet-reachable.
- **Secrets** (DB credentials, object storage keys, model registry tokens, JWT signing keys) are never hardcoded; sourced from environment variables / a secrets manager (Rule 9). `.env` files are gitignored.
- **Tenant isolation** is a security boundary, not just a data-modeling convenience (§7).
- **Role-based access control** on API routes: e.g., only "analyst"/"admin" roles can resolve/dismiss incidents; only "admin" can manage cameras/users.
- **Evidence access is audited.** Every read of `evidence.schema.json`-backed media should be logged (who, when, which incident), because evidence may be used in downstream investigative/legal contexts.
- **Face/Re-ID/ANPR are treated as sensitive personal-data categories.** Access to raw face/vehicle-identity matches is more tightly scoped (role + audit) than access to aggregate analytics (e.g., crowd counts).
- **Least-privilege between services.** Each service's credentials (DB user, storage bucket policy) are scoped to only what that service needs.

## 10. Model Versioning Strategy

- `model_metadata.schema.json` is the contract of record for versioning: every inference-producing stage records which model/version produced a given output.
- Models are treated as **pluggable providers** behind a stable per-stage interface (e.g., a `Detector` interface that a specific pretrained-model integration implements). Swapping a model version means implementing/registering a new provider, not changing pipeline code.
- A model registry (even a simple structured directory + metadata file for the MVP; a proper registry service for production) tracks: model name, version, source/license, supported hardware (GPU/CPU), input/output shape, and evaluation metrics (Rule 14).
- Rollback: the previous model version's metadata is retained so a regression can be reverted by re-pointing the provider config, not by redeploying code.
- This strategy is documented now; concrete registry implementation is deferred to the phase that implements the relevant AI module (Rule 15).

## 11. Evidence / Object Storage Strategy

- Evidence artifacts (clips, snapshots, tracks-as-video overlays) are large binaries and are **never** stored inline in the primary database. They are stored in object storage (S3-compatible; exact provider chosen in the implementation phase and verified against Rule 3) and referenced by URL/key inside `evidence.schema.json` records.
- Access to evidence objects goes through the backend (signed/short-lived URLs), not direct public bucket access, to preserve tenant isolation and audit logging (§9).
- Retention (§13) applies to object storage as well as the database — evidence lifecycle is a first-class policy, not an afterthought, given potential legal/investigative use.

## 12. Logging / Observability Strategy

- **Structured logging** (JSON logs with tenant_id, camera_id, stage name, correlation/trace id) across every service, per Rule 13.
- **Health checks** per service (liveness/readiness), and `camera_health.schema.json` specifically for camera/stream-level health surfaced to operators.
- **Metrics**: per-stage inference latency, end-to-end pipeline latency, throughput (frames/sec, events/sec), queue depth (once a message bus exists), false-positive/false-negative rates where ground truth is available (Rule 14).
- **Model/version metadata** (`model_metadata.schema.json`) attached to traces so a bad output can be traced back to a specific model version.
- **Correlation IDs** flow from ingestion through to alert, so a single incident can be traced across all contracts it touched.
- Observability is designed in from Phase 1 so it isn't retrofitted later; concrete tooling choice (e.g., a specific metrics/log stack) is deferred to the DevOps/QA phase and will be verified against Rule 3 before adoption.

## 13. Data Retention and Backup/Recovery Principles

- **Tiered retention**: raw video (short retention, e.g., rolling buffer), detections/tracks (medium retention, useful for baseline learning), events/incidents/evidence (longer retention, tenant-configurable, driven by investigative/compliance need).
- **Tenant-configurable retention windows** where legally/operationally appropriate, enforced by a scheduled purge process rather than manual deletion.
- **Evidence integrity**: once evidence is attached to an incident, it should not be silently purged by a generic retention job without an explicit hold/exception mechanism.
- **Backup/recovery**: database and object storage both require a documented backup cadence and a tested restore procedure before production hardening is considered complete (Rule 8 — nothing is "production ready" just because it was written). Concrete backup tooling/cadence is a production-hardening-phase decision, not a Phase 1 decision — this section only establishes the principle.

## 14. SIH MVP vs. Production Hardening vs. SaaS Deployment vs. Future Android

To avoid over-engineering the current phase (Rule 10) while still building real foundations, this architecture distinguishes four maturity tiers explicitly:

| Concern | SIH MVP (hackathon demo) | Production Hardening | SaaS Deployment | Future Android |
|---|---|---|---|---|
| Deployment | Single machine (stated dev hardware), possibly single tenant | Hardened services, health checks, real secrets management | Full multi-tenant isolation, billing/quota, per-tenant scaling | N/A (client only) |
| Data store | Local DB (e.g., single Postgres instance), local/dev object storage | Managed DB with backups, tested recovery | Multi-tenant schema/row isolation at scale, managed object storage | Consumes backend only |
| Auth | Basic token auth, one or few demo accounts | Full RBAC, audited access, secret rotation | Org-level user management, SSO-ready | Token-based mobile auth (§6) |
| Models | Pretrained, minimal calibration, CPU/GPU fallback on dev hardware | Versioned model registry, monitored drift | Same, plus per-tenant model config overrides | N/A |
| Observability | Basic logs + health checks | Full metrics/tracing/alerting stack | Multi-tenant dashboards, SLOs | N/A |
| Edge/Cloud split | Mostly co-located on one machine | Real edge/cloud split per §8 | Same, at fleet scale | N/A |
| Android | Not built | Not built (unless explicitly assigned) | Not built (unless explicitly assigned) | Built only when a phase explicitly assigns it, against the API contracts defined here |

This table exists so that later phases know which tier they are building for, and so "production ready" is never claimed for MVP-tier work (Rule 8).

## 15. Explicit Non-Goals of Phase 1

- No AI/CV code (detectors, trackers, classifiers) is implemented.
- No contract files are created, modified, or invented.
- No Android code is written.
- No concrete cloud provider, database engine, or message bus is committed to as final — candidates are named where useful for architectural reasoning, but selection/verification (Rule 3) happens in the implementation phase that needs them.
- No database migrations or running services are created in this phase.

## 16. Contract Inspection Notes (Non-Modifying)

The 23 real Contract v1.0 files were inspected in full (structure, required fields, enums, `$schema` draft version). All 23 are valid JSON, all declare `$schema: https://json-schema.org/draft/2020-12/schema`, and none contain absolutist/certainty language (no "criminal", "guilty", "terrorist" — consistent with Rule 6; enums like `face.match_status` and `reid.status` are explicitly probabilistic: `MATCHED/UNKNOWN/LOW_CONFIDENCE/NO_FACE` and `MATCH/POSSIBLE_MATCH/NO_MATCH/UNCERTAIN`). `model_metadata.status` includes `FALLBACK`, which directly supports the graceful-degradation design in §8. `camera_health.status` includes `DEGRADED`, likewise.

Observations that do not require or receive any contract change, only documentation awareness:
- `tenant_id` coverage is limited — see the correction in §7.
- Risk/Event relationship is bidirectional/co-produced — see the note in §4.
- 9 of 23 contracts declare `title`/`description`/`$id`; 14 do not. 8 of 23 set `additionalProperties: false`; 15 leave the object open. This is an internal inconsistency in the contract set itself, reported here for the contract owner's awareness — it is not something this architecture phase alters.
- `docs/CONTRACTS.md` was referenced as uploaded but was not present in the actual upload (only `contracts.zip`, containing the 23 schema files, arrived). This document has been reconciled against the schema files directly; if `docs/CONTRACTS.md` exists and is provided later, it should be cross-checked against this section.

## 17. Traceability to This Phase's Requirements

Every numbered item in the Phase 1 task (1–15) is addressed as follows:

1. Overall architecture — §2
2. Module boundaries — `docs/SYSTEM_DESIGN.md`
3. Data flow between modules — §4
4. Module → contract mapping — §4 (table), detailed per-module in `docs/SYSTEM_DESIGN.md`
5. M1–M6 responsibilities — `docs/MODULE_OWNERSHIP.md`
6. API-first architecture — §5
7. Future Android architecture (undocumented, unimplemented) — §6
8. SaaS/multi-tenant architecture — §7
9. Edge–cloud architecture — §8
10. Model versioning strategy — §10
11. Evidence/object storage strategy — §11
12. Logging/observability strategy — §12
13. Security boundaries — §9
14. Retention and backup/recovery principles — §13
15. MVP vs. production vs. SaaS vs. Android distinction — §14
