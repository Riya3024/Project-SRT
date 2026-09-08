"""
Project SRT — full Tier 1 pipeline demo: Phase 1 + Phase 2 + Phase 3.

    VideoSource -> Detector+Tracker -> MovementFeatures -> BehaviorAnalyzer
        -> ZoneEngine -> ContextEngine -> BaselineStore/AnomalyEngine
        -> CrowdEngine -> RiskEngine -> Phase3Pipeline (Event/Incident/Evidence/Alert)

Usage (from repo root, with venv activated and requirements-cv.txt installed):

    python scripts/run_full_pipeline_demo.py --source path/to/video.mp4 --output out.mp4
    python scripts/run_full_pipeline_demo.py --source 0          # webcam
    python scripts/run_full_pipeline_demo.py --source rtsp://...  # RTSP stream

Every call in this file was verified against the real function/method
signatures in this repository (via `inspect.signature`) before being wired
— see docs/HACKATHON_TIER1_PHASE3.md for the exact signatures checked.

Known, honestly-documented limitation (section 34 of the Phase 3 spec): no
zone geometry is configured here (`ZoneEngine(zones=[])`), because this
generic demo has no site-specific camera layout to draw polygons against.
Every track therefore resolves to `zone_id=None` / `is_restricted=False`,
which means restricted-zone-entry events/alerts cannot fire from this demo
script until real zone polygons are supplied via `--zones-file` or
equivalent (not yet implemented). Anomaly/behavior-driven events (running,
sudden movement, possible fall/altercation) are unaffected by this and can
still fire. This script has NOT been executed against a real video in this
sandbox (no GPU/model download here) — see the Phase 3 report for the exact
verification status.
"""

from __future__ import annotations

import argparse
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

import cv2

from services.anomaly_detection.anomaly_engine import AnomalyEngine
from services.baseline.baseline_engine import BaselineKey, BaselineStore
from services.behavior_intelligence.behavior_analyzer import classify_single_track
from services.behavior_intelligence.movement_features import compute_movement_features
from services.common.annotate import annotate_frame
from services.common.config import PipelineConfig
from services.common.phase2_config import Phase2Config
from services.common.phase3_config import Phase3Config
from services.common.phase3_pipeline import Phase3Pipeline
from services.context.context_engine import TimeBucket, build_context, time_bucket_for_hour
from services.crowd_analytics.crowd_engine import summarize_crowd
from services.ingestion.video_source import VideoSource
from services.risk_engine.risk_engine import compute_risk
from services.tracking.tracker import Tracker
from services.zones.zone_engine import Zone, ZoneEngine, ZoneType

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("full_pipeline_demo")


def main() -> None:
    parser = argparse.ArgumentParser(description="Project SRT full Tier 1 pipeline demo (Phase 1+2+3)")
    parser.add_argument("--source", required=True, help="MP4 path, webcam index, or RTSP URL")
    parser.add_argument("--output", default=None, help="Optional annotated output MP4 path")
    parser.add_argument("--camera-id", default="DEMO-CAMERA-01")
    parser.add_argument("--model", default=None, help="Override MODEL_PATH")
    parser.add_argument("--device", default=None, choices=["auto", "cpu", "cuda"])
    parser.add_argument("--frame-skip", type=int, default=None)
    args = parser.parse_args()

    config = PipelineConfig()
    if args.model:
        config = PipelineConfig(**{**config.__dict__, "model_path": args.model})
    if args.device:
        config = PipelineConfig(**{**config.__dict__, "device": args.device})
    if args.frame_skip is not None:
        config = PipelineConfig(**{**config.__dict__, "frame_skip": args.frame_skip})

    phase2_config = Phase2Config()
    phase3_config = Phase3Config()
    camera_id = args.camera_id
    source_path = args.source if isinstance(args.source, str) and not args.source.isdigit() else None

    tracker = Tracker(config).load()
    logger.info("Device in use: %s", tracker.device)

    # No site-specific zone polygons configured for this generic demo — see
    # module docstring above. Real deployments should load Zone(...) objects
    # (polygon, zone_type=NORMAL/RESTRICTED) per camera here instead.
    zone_engine = ZoneEngine(zones=[])
    zones_by_id: dict[str, Zone] = {}

    baseline_store = BaselineStore()
    anomaly_engine = AnomalyEngine(baseline_store, phase2_config)
    pipeline3 = Phase3Pipeline(phase3_config, phase2_config)

    writer = None
    frame_count = 0
    total_latency = 0.0
    pipeline_start = time.perf_counter()

    with VideoSource(
        args.source,
        frame_skip=config.frame_skip,
        resize_width=config.resize_width,
        resize_height=config.resize_height,
    ) as source:
        for frame in source.frames():
            result = tracker.track(frame.image, frame.frame_number, frame.timestamp)
            total_latency += result.inference_latency_s
            frame_count += 1

            wall_clock = datetime.now(timezone.utc)
            time_bucket = time_bucket_for_hour(wall_clock.hour, phase2_config)
            is_night = time_bucket == TimeBucket.NIGHT

            history_by_id = {h.track_id: h for h in result.history}
            behaviors_by_track: dict[int, list] = {}
            classes_by_zone: dict[str, list[str]] = defaultdict(list)

            for t in result.tracks:
                zone_event = zone_engine.update(t.track_id, t.bbox, frame.timestamp)
                zone = zones_by_id.get(zone_event.zone_id) if zone_event.zone_id else None
                zone_type_value = zone.zone_type.value if zone else None
                is_restricted = zone is not None and zone.zone_type == ZoneType.RESTRICTED
                if zone_event.zone_id:
                    classes_by_zone[zone_event.zone_id].append(t.class_name)

                if t.class_name != "person":
                    continue
                h = history_by_id.get(t.track_id)
                if h is None:
                    continue

                feats = compute_movement_features(h, config.stationary_speed_threshold)
                behavior_obs = classify_single_track(feats, frame.timestamp, config)
                behaviors_by_track[t.track_id] = behavior_obs
                behavior_strs = [b.behavior for b in behavior_obs]

                # ContextObservation is currently built for traceability/logging;
                # AnomalyEngine takes its inputs directly (features + context_flags)
                # rather than the ContextObservation object itself.
                build_context(
                    t.track_id, "person", behavior_strs, camera_id,
                    zone_event.zone_id, zone_type_value, frame.timestamp,
                    phase2_config, wall_clock=wall_clock,
                )

                features = {"speed_px_s": feats.speed_px_s, "dwell_seconds": zone_event.dwell_seconds}
                context_flags = []
                if is_restricted:
                    context_flags.append("restricted_zone_presence")
                if is_night:
                    context_flags.append("night_time_activity")

                zone_key = zone_event.zone_id or "NONE"
                anomaly = anomaly_engine.evaluate(
                    t.track_id, camera_id, zone_key, time_bucket, features, context_flags, frame.timestamp,
                )
                # Update baseline AFTER evaluating against it, to avoid a sample
                # trivially "confirming" its own anomaly score.
                for feature_name, value in features.items():
                    baseline_store.update(BaselineKey(camera_id, zone_key, time_bucket, feature_name), value, frame.timestamp)

                risk = compute_risk(
                    t.track_id, anomaly, behavior_strs, is_restricted, is_night,
                    t.confidence, phase2_config, frame.timestamp,
                )

                phase3_result = pipeline3.process_observation(
                    track_id=t.track_id, camera_id=camera_id, anomaly=anomaly, risk=risk,
                    behaviors=behavior_strs, timestamp=frame.timestamp,
                    is_restricted_zone=is_restricted, source_path=source_path, wall_clock=wall_clock,
                )
                if phase3_result.alert:
                    print(f"\n{phase3_result.alert.message}\n")

            for zone_id, classes in classes_by_zone.items():
                crowd = summarize_crowd(camera_id, zone_id, frame.timestamp, classes)
                baseline_store.update(
                    BaselineKey(camera_id, zone_id, time_bucket, "person_count"),
                    float(crowd.person_count), frame.timestamp,
                )

            pipeline3.expire_stale(wall_clock)

            for t in result.tracks:
                behavior_str = ", ".join(b.behavior for b in behaviors_by_track.get(t.track_id, []))
                print(
                    f"frame={frame.frame_number} t={frame.timestamp:.2f}s "
                    f"{t.class_name.upper()} #{t.track_id} conf={t.confidence:.2f} "
                    f"behavior=[{behavior_str}]"
                )

            if args.output:
                current_fps = frame_count / max(time.perf_counter() - pipeline_start, 1e-6)
                annotated = annotate_frame(frame.image, result.tracks, behaviors_by_track, current_fps)
                if writer is None:
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(args.output, fourcc, max(frame.source_fps, 1.0), (frame.width, frame.height))
                writer.write(annotated)

    if writer is not None:
        writer.release()

    elapsed = time.perf_counter() - pipeline_start
    avg_fps = frame_count / elapsed if elapsed > 0 else 0.0
    avg_latency_ms = (total_latency / frame_count * 1000) if frame_count else 0.0
    logger.info(
        "Done. frames=%d elapsed=%.2fs avg_fps=%.2f avg_inference_latency=%.1fms device=%s",
        frame_count, elapsed, avg_fps, avg_latency_ms, tracker.device,
    )


if __name__ == "__main__":
    main()
