# Project SRT — Hackathon Tier 1, Phase 3

Events + Incidents + Evidence + Alerts, consuming Phase 1 (detection/tracking/behavior) and
Phase 2 (context/zones/baseline/anomaly/crowd/risk) output.

## What's implemented

| Module | File | Contract |
|---|---|---|
| Event Engine | `services/incident_intelligence/event_engine.py` | `contracts/event.schema.json` |
| Incident Engine | `services/incident_intelligence/incident_engine.py` | `contracts/incident.schema.json` |
| Evidence Engine | `services/evidence/evidence_engine.py` | `contracts/evidence.schema.json` |
| Alert Engine | `services/alerts/alert_engine.py` | `contracts/alert.schema.json` |
| Orchestration | `services/common/phase3_pipeline.py` (`Phase3Pipeline`) | wires all four together |
| Config | `services/common/phase3_config.py` (`Phase3Config`) | correlation windows, evidence buffer, alert cooldown |
| Serialization | `services/common/contract_utils.py` (`to_contract_dict`) | drops `None`-valued optional fields so non-nullable-but-optional contract fields (e.g. `incident.tenant_id`) serialize correctly |

**Why Event lives in `services/incident_intelligence/`, not a new `services/event/`:** the design
doc (`docs/SYSTEM_DESIGN.md` §17) explicitly left this as an implementation decision — Event
"produced within `services/risk_engine/` or a dedicated `services/event/` boundary, decided at
implementation time." Since neither is a populated module and `incident_intelligence/` already
owns the closely related Incident Engine, Event lives there rather than creating a new top-level
service directory (the Phase 3 spec explicitly says not to create duplicate service directories).

## Contract fidelity — verified, not assumed

Unlike the Phase 1/2 drafts (which flagged their field shapes as "best-effort, not verified
against the real contract"), every Phase 3 dataclass was checked field-for-field against the
actual `contracts/*.schema.json` files before being written, and there's a standing regression
test (`tests/services/test_phase3_contract_compliance.py`) that validates real output instances
against the real schemas using `jsonschema.Draft202012Validator` — not just a by-eye comparison.

Two real bugs were caught this way during development and are now covered by tests:
- `RiskObservation.risk_level` is a `RiskLevel` enum; naive `str(risk_level)` produces
  `"RiskLevel.HIGH"`, not `"HIGH"`. Fixed to use `.value` everywhere it crosses into a Phase 3
  contract field.
- `IncidentObservation.tenant_id` defaults to `None`, but `incident.schema.json` declares that
  field as plain `{"type": "string"}` (not nullable) — serializing `null` violated the schema.
  Fixed via `to_contract_dict()`, which drops `None`-valued keys instead of emitting `null`.

One deliberate departure from the *spec's own illustrative wording* (not from the contract): the
spec's section 3 suggests event states like OPEN/UPDATED/RESOLVED, but the real
`event.schema.json` enum is `DETECTED/CONFIRMED/DISMISSED/ESCALATED` — the real contract is the
one that was implemented against. See `event_engine.py`'s docstring for the exact lifecycle
mapping chosen (a never-confirmed, timed-out event closes as `DISMISSED`; a confirmed one keeps
its status — the contract has no "resolved" state for events, only for incidents).

## Deduplication / lifecycle, in one paragraph each

- **Event dedup:** correlated by `(camera_id, track_id, event_type)`. A repeat observation of the
  same key within `event_correlation_window_seconds` updates the *same* `event_id` instead of
  creating a new one. `DETECTED` → `CONFIRMED` after `event_confirm_min_observations` repeats;
  `CRITICAL` risk escalates to `ESCALATED` immediately, on the very first observation too (this
  was a real bug — the escalation check originally only lived on the "update" branch, not
  "create"; caught by `test_critical_risk_escalates_immediately`).
- **Incident grouping:** same camera + (shared `track_id` OR shared `event_type`) within
  `incident_correlation_window_seconds`. Severity only ever escalates, never auto-downgrades.
- **Evidence:** always writes a real JSON manifest to `Phase3Config.evidence_storage_dir`
  (`event_id`/`incident_id`/`camera_id`/time window/source reference — never fabricated). If a
  real source video path exists and `cv2` is importable, additionally attempts a real
  frame-range MP4 extraction; any failure anywhere in that path falls back to a `FRAME`-typed
  record referencing the manifest, and never crashes the caller.
- **Alert dedup/cooldown:** keyed by `incident_id`, gated on `severity >=
  Phase3Config.alert_min_risk_level` AND the triggering event being `CONFIRMED`/`ESCALATED`
  (never a bare `DETECTED` blip). A cooldown window suppresses repeats, except a severity
  escalation always overrides an active cooldown.

## Responsible language

`alert_engine.py` never emits certainty/criminal-intent language — enforced by a standing
regression test (`tests/services/alerts/test_alert_engine.py::TestAlertLinkageAndLanguage`) that
checks generated messages against the spec's explicit forbidden-phrase list ("criminal detected",
"kidnapper detected", etc.) and confirms probabilistic phrasing ("potential"/"possible") appears
instead.

## How to run the tests

```
pytest tests/services/ -v
```

97 tests: 45 pre-existing (Phase 1 + Phase 2) + 52 new (Phase 3: 10 event, 11 incident, 10
evidence, 13 alert, 4 integration, 4 contract-compliance). Zero regressions.

## How to run the demo

```
pip install -r requirements-cv.txt   # then install torch per your CUDA driver
python scripts/run_full_pipeline_demo.py --source path/to/video.mp4 --output out.mp4
```

**Honest status: not executed against a real video in the environment this was built in** — no
GPU, no downloaded model weights, no sample video available there. Every function/method call in
`run_full_pipeline_demo.py` was individually verified against the real signatures in this repo
(via `inspect.signature`, not guessed), and the Phase 2→3 glue logic it contains was additionally
exercised end-to-end with synthetic stand-ins for Phase 1's `TrackedObject`/`TrackRecord` — 12
iterations across two scenarios, zero exceptions. What that check does *not* cover: whether the
real `Detector`/`Tracker` model-loading and inference path itself runs cleanly on your machine —
that was already the same honestly-flagged gap in Phase 1's own report, unchanged here.

## Known limitations

- **No zone geometry configured in the demo script.** `ZoneEngine(zones=[])` — every track
  resolves to `zone_id=None`, so restricted-zone-entry events/alerts cannot fire from
  `run_full_pipeline_demo.py` until real per-camera zone polygons are supplied. Behavior/anomaly-
  driven events (running, sudden movement, possible fall/altercation) are unaffected.
- **Cold-start baseline.** Same limitation already flagged in Phase 2: a freshly started stream
  has no baseline history, so early anomaly scores are near zero until enough samples accumulate
  per `(camera_id, zone_id, time_bucket, feature_name)` key.
- **No object-storage backend for evidence** — local filesystem only, by design for this
  hackathon phase (`EvidenceEngine.writer` is injectable specifically so this can change later
  without touching correlation logic).
- **`AnomalyEngine.isolation_forest_score()`** (Phase 2) still isn't wired into `evaluate()` by
  default — unchanged from Phase 2's own documented status.
