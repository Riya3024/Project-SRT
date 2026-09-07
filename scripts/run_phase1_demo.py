"""
Project SRT — Combined Phase 1 demo runner.

Usage (from repo root, with venv activated and requirements-cv.txt installed):

    python scripts/run_phase1_demo.py --source path/to/video.mp4 --output out.mp4
    python scripts/run_phase1_demo.py --source 0          # webcam
    python scripts/run_phase1_demo.py --source rtsp://...  # RTSP stream

Prints per-frame detections/tracks/behaviors to stdout and writes an
annotated video to --output (if given). Reports approximate FPS and
inference latency at the end, per section 17/19.
"""

from __future__ import annotations

import argparse
import logging
import math
import time

import cv2

from services.behavior_intelligence.behavior_analyzer import (
    BehaviorObservation,
    classify_single_track,
)
from services.behavior_intelligence.movement_features import compute_movement_features
from services.common.annotate import annotate_frame
from services.common.config import PipelineConfig
from services.ingestion.video_source import VideoSource
from services.tracking.tracker import Tracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("phase1_demo")


def _proximity_altercation_check(
    tracked, history_by_id, config, timestamp
) -> list[BehaviorObservation]:
    """Real proximity + closing-speed check across currently visible people (section 13)."""
    people = [t for t in tracked if t.class_name == "person"]
    obs: list[BehaviorObservation] = []
    for i in range(len(people)):
        for j in range(i + 1, len(people)):
            a, b = people[i], people[j]
            ax = (a.bbox[0] + a.bbox[2]) / 2.0
            ay = (a.bbox[1] + a.bbox[3]) / 2.0
            bx = (b.bbox[0] + b.bbox[2]) / 2.0
            by = (b.bbox[1] + b.bbox[3]) / 2.0
            dist = math.hypot(ax - bx, ay - by)
            if dist > config.altercation_proximity_px:
                continue

            rec_a, rec_b = history_by_id.get(a.track_id), history_by_id.get(b.track_id)
            if rec_a is None or rec_b is None:
                continue
            fa = compute_movement_features(rec_a, config.stationary_speed_threshold)
            fb = compute_movement_features(rec_b, config.stationary_speed_threshold)
            if fa.speed_px_s >= config.altercation_closing_speed_px_s / 2 and \
               fb.speed_px_s >= config.altercation_closing_speed_px_s / 2:
                obs.append(
                    BehaviorObservation(
                        track_id=a.track_id,
                        behavior="possible_physical_altercation",
                        confidence=0.45,
                        timestamp=timestamp,
                        supporting_features={
                            "other_track_id": b.track_id,
                            "proximity_px": dist,
                            "note": "requires_operator_review",
                        },
                    )
                )
    return obs


def main() -> None:
    parser = argparse.ArgumentParser(description="Project SRT Phase 1 demo")
    parser.add_argument("--source", required=True, help="MP4 path, webcam index, or RTSP URL")
    parser.add_argument("--output", default=None, help="Optional annotated output MP4 path")
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

    tracker = Tracker(config).load()
    logger.info("Device in use: %s", tracker.device)

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

            history_by_id = {h.track_id: h for h in result.history}
            behaviors_by_track: dict[int, list[BehaviorObservation]] = {}
            for h in result.history:
                if h.class_name != "person":
                    continue
                feats = compute_movement_features(h, config.stationary_speed_threshold)
                behaviors_by_track[h.track_id] = classify_single_track(feats, frame.timestamp, config)

            altercations = _proximity_altercation_check(result.tracks, history_by_id, config, frame.timestamp)
            for obs in altercations:
                behaviors_by_track.setdefault(obs.track_id, []).append(obs)

            for t in result.tracks:
                behavior_str = ", ".join(b.behavior for b in behaviors_by_track.get(t.track_id, []))
                print(
                    f"frame={frame.frame_number} t={frame.timestamp:.2f}s "
                    f"{t.class_name.upper()} #{t.track_id} conf={t.confidence:.2f} "
                    f"bbox={tuple(round(v) for v in t.bbox)} "
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
