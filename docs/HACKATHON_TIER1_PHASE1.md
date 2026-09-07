# Project SRT — Hackathon Tier 1 — Combined Phase 1

Video Ingestion + Detection + Tracking + Human Behavior Intelligence.

**Status when this doc was written: code drafted, NOT executed against a real
model or GPU, NOT committed.** See "How this was produced" at the bottom
before treating anything here as verified.

## Pipeline

```
VideoSource -> FrameSampler (built into VideoSource) -> Tracker (YOLO + ByteTrack)
  -> TrackHistoryStore -> MovementFeatures -> BehaviorAnalyzer -> AnnotatedOutput
```

Detection and tracking are combined via Ultralytics' `model.track(...,
tracker="bytetrack.yaml")`, which runs YOLO detection and ByteTrack
association in one call — see `services/tracking/tracker.py` for why this was
chosen over a standalone ByteTrack package.

## Install

```bash
# from repo root, existing .venv activated
pip install -r services/requirements-cv.txt
# then install torch/torchvision for your platform: https://pytorch.org/get-started/locally/
```

Ultralytics downloads `yolov8n.pt` (or whichever `MODEL_PATH` you set) on
first run if it isn't already cached locally — this needs network access at
least once.

## Configuration

Environment variables read by `services/common/config.py` (add these to
`.env.example` with placeholder values when integrating):

| Variable | Meaning | Default |
|---|---|---|
| `VIDEO_SOURCE` | file path, webcam index, or RTSP URL | `0` |
| `FRAME_SKIP` | process every Nth+1 frame | `0` |
| `TARGET_FPS` | throttle processing rate; `0` = unthrottled | `0` |
| `RESIZE_WIDTH` / `RESIZE_HEIGHT` | resize before inference; `0` height preserves aspect | `960` / `0` |
| `MODEL_PATH` | Ultralytics model file/name | `yolov8n.pt` |
| `CONFIDENCE_THRESHOLD` | detection confidence cutoff | `0.4` |
| `DEVICE` | `auto` \| `cpu` \| `cuda` | `auto` |
| `TRACKER` | Ultralytics tracker config | `bytetrack.yaml` |
| `TRACK_HISTORY_LEN` | samples kept per track | `90` |
| `TRACK_LOST_TTL_FRAMES` | frames before a track is dropped | `30` |
| `RUNNING_SPEED_THRESHOLD`, `WALKING_SPEED_THRESHOLD`, `SUDDEN_MOVEMENT_ACCEL_THRESHOLD`, `DIRECTION_CHANGE_THRESHOLD_DEG`, `STATIONARY_SPEED_THRESHOLD`, `LOITERING_DWELL_SECONDS`, `FALL_VERTICAL_RATIO_THRESHOLD`, `ALTERCATION_PROXIMITY_PX`, `ALTERCATION_CLOSING_SPEED_PX_S` | behavior thresholds, pixel/sec units in resized-frame space | see `config.py` |

## Run the demo

```bash
python scripts/run_phase1_demo.py --source path/to/cctv_clip.mp4 --output annotated_out.mp4
python scripts/run_phase1_demo.py --source 0                       # webcam
python scripts/run_phase1_demo.py --source rtsp://camera-ip/stream # RTSP
```

Prints per-frame `CLASS #track_id conf=... bbox=... behavior=[...]` lines to
stdout, writes an annotated MP4 if `--output` is given, and logs approximate
FPS / inference latency / device (CPU or CUDA) at the end.

## Run tests

```bash
python -m pytest tests/services/ -v
```

`test_track_history.py`, `test_movement_features.py`, and
`test_behavior_analyzer.py` are pure-Python and deterministic — no model or
GPU required. A `test_detector.py` / `test_tracker.py` pair using a mocked
Ultralytics model (per section 18: "GPU/CPU fallback", "detector
initialization", "output structure") still needs to be written once the real
model is confirmed loadable in your environment — not included yet.

## Behavior output shape

```json
{
  "track_id": 17,
  "behavior": "running",
  "confidence": 0.84,
  "timestamp": 12.4,
  "supporting_features": {"speed_px_s": 260.3, "direction_deg": 91.2}
}
```

This matches the example in the phase spec's section 15. **Not yet reconciled
against `contracts/activity.schema.json` / `contracts/behavior_observation.schema.json`**
— field names/types here are a best-effort guess, not a verified match. Run
`python scripts/validate_contracts.py` and diff this shape against the real
schemas before wiring this into anything contract-consuming.

## Known limitations

- Speed/direction/dwell are in resized-frame pixel units, not real-world
  units — no camera calibration step exists yet.
- The possible-altercation check is a shallow proximity + simultaneous
  acceleration heuristic, not pose-based interaction analysis.
- Pose estimation (optional per section 12) is not implemented in this pass.
- No CPU-fallback / GPU-detection test has actually been run — `Detector`/`Tracker`
  auto-select `cuda` if `torch.cuda.is_available()`, but this was never
  exercised against a live PyTorch/CUDA install.
- RTSP is "should work" via `cv2.VideoCapture`, not demo-tested against a real
  RTSP source.

## How this was produced

This code was written and logic-checked (via plain assertions, not pytest —
pytest wasn't installable) in a network-isolated, GPU-less sandbox. It was
**never run against the real repository, a real video file, a real YOLO
model, or a GPU**, and was **never committed or pushed** — that sandbox has
no git remote access either. Treat this as a drafted patch to review, adapt
to the actual `contracts/*.json` field names, and validate on your machine
(ideally via Claude Code, which has real filesystem/git/GPU access), not as
a verified "Phase 1 DONE."
