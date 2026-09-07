# Project SRT — Hackathon Tier 1 — Phase 2

Context + Zones + Baseline + Anomaly + Risk.

**Status: code drafted and logic-verified manually (pytest unavailable — no
network in the authoring sandbox), NOT run against the real Phase 1
implementation, NOT committed.** See "How this was produced" before trusting
anything here as verified against your actual repo.

## Pipeline

```
Phase 1 TrackedObject + BehaviorObservation
  -> ContextEngine (WHO/WHAT/WHERE/WHEN)
  -> ZoneEngine (polygon membership, entry/exit, dwell)
  -> BaselineStore (incremental mean/variance per camera/zone/time_bucket/feature)
  -> AnomalyEngine (z-score vs baseline + optional Isolation Forest + context flags)
  -> RiskEngine (fuses anomaly + behavior + zone + time -> score/level/confidence)
```

## IMPORTANT — integration gap with the real Phase 1

This was built against **my own Phase 1 draft's dataclasses**
(`TrackedObject`, `TrackRecord`, `MovementFeatures`, `BehaviorObservation`
from the previous deliverable), not against whatever actually exists in
`Riya3024/Project-SRT` right now. Before wiring this in:

1. Confirm what Phase 1 code actually landed in the repo (field names may
   differ from my draft, especially if Claude Code or you adjusted anything
   during integration).
2. Update the call sites in `context_engine.build_context()` and the (not
   yet written) Phase 1→2 wiring script to match the real signatures.
3. Reconcile field names against `contracts/context.schema.json`,
   `contracts/zone_event.schema.json`, `contracts/baseline.schema.json`,
   `contracts/anomaly.schema.json`, `contracts/crowd.schema.json`,
   `contracts/risk.schema.json` — none of which I've read directly.

## A bug this manual verification caught

`ZoneEngine.update()`'s dwell calculation originally used
`state.entry_timestamp or timestamp`, which silently discarded a valid
`entry_timestamp == 0.0` (Python truthiness treats `0.0` as falsy) and
reported 0-second dwell for anything entering at the very start of a clip.
Fixed to an explicit `is not None` check. This is exactly the kind of bug
that "code exists" doesn't catch — it needed the assertion run.

## Configuration

New env vars (`services/common/phase2_config.py`) — add to `.env.example`:

`DWELL_ALERT_SECONDS`, `LOITERING_SECONDS`, `MORNING_START_HOUR`,
`AFTERNOON_START_HOUR`, `EVENING_START_HOUR`, `NIGHT_START_HOUR`,
`MIN_BASELINE_SAMPLES`, `BASELINE_HIGH_CONFIDENCE_SAMPLES`,
`ANOMALY_ZSCORE_THRESHOLD`, `ANOMALY_SCORE_THRESHOLD`,
`ISOLATION_FOREST_MIN_SAMPLES`, `ISOLATION_FOREST_CONTAMINATION`,
`RISK_LOW_MAX`, `RISK_MEDIUM_MAX`, `RISK_HIGH_MAX`.

## Design notes

- **Baseline** uses Welford's online algorithm — O(1) memory per
  (camera, zone, time_bucket, feature) key, no raw sample history retained
  (section 14).
- **Anomaly** requires `sample_count >= 2` before computing any z-score at
  all, and confidence ramps from baseline sample count — an anomaly with an
  empty/thin baseline always scores `0.0`, never a guessed value (section 18).
- **Isolation Forest** (`AnomalyEngine.isolation_forest_score`) is optional:
  returns `None` if scikit-learn isn't installed or there aren't
  `ISOLATION_FOREST_MIN_SAMPLES` yet — treat `None` as "no ML signal," not
  as zero. Not wired into `evaluate()` by default; call it separately and
  fold the result into your own `context_flags`/features if you want it in
  the main score. Not exercised in this session (scikit-learn not installed
  in the sandbox either).
- **Crowd**: `summarize_crowd()` only counts. It intentionally has no
  opinion on whether a count is unusual — that only happens if you push
  `person_count` (etc.) through `AnomalyEngine.evaluate()` like any other
  feature, against its own baseline (section 22 test:
  `test_crowd_count_alone_is_not_automatically_anomalous`).
- **Risk vs. confidence** are computed independently:
  `risk_score`/`risk_level` come from anomaly score + behavior + zone + time
  weights; `confidence` comes from `(anomaly.confidence + detection_confidence) / 2`.
  A HIGH/CRITICAL risk level with low confidence is a valid, expected output.

## Tests

```bash
python -m pytest tests/services/test_zone_engine.py tests/services/test_baseline_engine.py \
    tests/services/test_anomaly_engine.py tests/services/test_risk_engine.py -v
```

29 test cases across the four new modules, covering: point-in/out-of-polygon,
zone entry/exit/dwell, disabled zones, incremental mean/variance, confidence
ramp, insufficient-sample handling, normal vs. deviant anomaly scoring,
explanation generation, the crowd-count guard, all four risk levels,
contributor dedup, and confidence-independent-of-level. **Not run through
pytest itself** (unavailable, no network) — instead re-implemented as plain
assertions against the real modules and run directly; all passed after the
dwell-bug fix above. Run the real pytest suite yourself before trusting this
number.

## Not implemented (explicitly out of scope this phase)

Event engine, incident grouping, evidence clips, alerts, WebSockets, command
center, face recognition, ANPR, Re-ID, cross-camera identity — all deferred
to Phase 3 per your instructions.

## How this was produced

Same constraints as Phase 1: network-isolated, GPU-less sandbox, no access
to your actual GitHub repo or its current `feature/hackathon-tier1` state.
Nothing here was committed or pushed. The logic was verified by writing
pytest-style test files (included) and *separately* re-running equivalent
assertions directly via `python3 -c ...` since pytest could not be
installed — that run caught and fixed one real bug (the dwell calculation
above). Treat this as a reviewed draft, not a verified "Phase 2 DONE."
