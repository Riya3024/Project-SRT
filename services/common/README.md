# Common

Shared utilities used across the Combined Phase 1 (hackathon Tier 1) modules — created
because `services/ingestion`, `services/detection`, `services/tracking`, and
`services/behavior_intelligence` all depend on the same pipeline configuration, and the
demo runner needs one shared annotation/visualization helper rather than each module
reimplementing it.

- `config.py` — `PipelineConfig`, environment-driven configuration for video source, frame
  sampling, detection thresholds, tracker settings, and behavior thresholds (see
  `../../.env.example` for keys to add). Deliberately kept separate from
  `../../backend/app/config.py`, which configures the FastAPI backend service
  (host/port/log level) — no field overlap between the two.
- `annotate.py` — `annotate_frame()`, draws bounding boxes, class/track labels, and behavior
  text onto a frame for the annotated demo output (`scripts/run_phase1_demo.py --output`).

See `../../docs/HACKATHON_TIER1_PHASE1.md` for full Phase 1 status/known limitations.
