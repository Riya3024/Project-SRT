#!/usr/bin/env python3
"""Validate the 23 frozen Contract v1.0 JSON Schema files.

Rule 14 (Contract Validation): this script is READ-ONLY. It discovers the
contract files, parses them as JSON, and validates that each is a
syntactically well-formed JSON Schema document (using the same jsonschema
library / Draft 2020-12 validator the contracts declare). It never writes to,
rewrites, or reformats any contract file, under any circumstance.

Usage:
    python scripts/validate_contracts.py
    (exit code 0 = all pass, 1 = one or more contracts failed)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "contracts"

EXPECTED_CONTRACTS = [
    "common.schema.json",
    "detection.schema.json",
    "tracking.schema.json",
    "activity.schema.json",
    "behavior_observation.schema.json",
    "context.schema.json",
    "baseline.schema.json",
    "anomaly.schema.json",
    "crowd.schema.json",
    "zone_event.schema.json",
    "risk.schema.json",
    "event.schema.json",
    "incident.schema.json",
    "evidence.schema.json",
    "alert.schema.json",
    "vehicle.schema.json",
    "anpr.schema.json",
    "face.schema.json",
    "reid.schema.json",
    "camera_health.schema.json",
    "operator_feedback.schema.json",
    "api_response.schema.json",
    "model_metadata.schema.json",
]


def validate_contracts(contracts_dir: Path = CONTRACTS_DIR) -> tuple[bool, list[str]]:
    """Validate every expected contract file. Returns (all_ok, messages).

    Never mutates any file in contracts_dir.
    """
    messages: list[str] = []
    all_ok = True

    for filename in EXPECTED_CONTRACTS:
        path = contracts_dir / filename

        if not path.exists():
            all_ok = False
            messages.append(f"MISSING   {filename}")
            continue

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            all_ok = False
            messages.append(f"READ FAIL {filename}: {exc}")
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            all_ok = False
            messages.append(f"INVALID JSON {filename}: {exc}")
            continue

        try:
            Draft202012Validator.check_schema(data)
        except SchemaError as exc:
            all_ok = False
            messages.append(f"INVALID JSON SCHEMA {filename}: {exc.message}")
            continue

        messages.append(f"OK        {filename}")

    # Flag any *.schema.json in the directory that isn't in our expected list,
    # without treating it as a failure — just informational (contract set may
    # grow only with explicit project-lead authorization, per Rule 1).
    on_disk = (
        {p.name for p in contracts_dir.glob("*.schema.json")} if contracts_dir.exists() else set()
    )
    unexpected = sorted(on_disk - set(EXPECTED_CONTRACTS))
    for name in unexpected:
        messages.append(f"UNEXPECTED (not in frozen list of 23): {name}")

    return all_ok, messages


def main() -> int:
    if not CONTRACTS_DIR.exists():
        print(f"ERROR: contracts directory not found at {CONTRACTS_DIR}")
        return 1

    ok, messages = validate_contracts()
    print(f"Contract validation — {CONTRACTS_DIR}")
    print("-" * 60)
    for m in messages:
        print(m)
    print("-" * 60)
    pass_count = sum(1 for m in messages if m.startswith("OK"))
    print(f"{pass_count}/{len(EXPECTED_CONTRACTS)} contracts valid")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
