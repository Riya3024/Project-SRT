#!/usr/bin/env python3
"""Safe GPU/CPU environment diagnostic (Rule 19).

What this does:
  1. Runs `nvidia-smi` (if present) to report whether an NVIDIA GPU and driver
     are visible to the OS at all. This works without any Python ML library
     installed.
  2. If a Python ML framework (PyTorch) happens to already be installed, it
     also reports whether CUDA is available to that framework. It does NOT
     install PyTorch or any other framework as a side effect of running this
     script — Project SRT has not committed to a specific ML framework yet
     (that choice belongs to M1/M2 in a later phase); this script simply
     checks if a compatible one is present and reports the CUDA status,
     without downloading or installing anything.

What this deliberately does NOT do (Rule 19):
  - Does not install any ML library.
  - Does not download or load any model weights.
  - Does not run any training or inference.

If no GPU is found, or no ML framework is installed, this script exits 0
(informational, not a failure) — Rule 5 requires the environment to remain
usable on CPU-only machines.
"""

from __future__ import annotations

import shutil
import subprocess


def check_nvidia_smi() -> None:
    nvidia_smi_path = shutil.which("nvidia-smi")
    if nvidia_smi_path is None:
        print("[nvidia-smi] not found on PATH — no NVIDIA driver detected, or not installed.")
        print("             This is expected on non-GPU developer machines (Rule 5).")
        return

    try:
        result = subprocess.run(
            [
                nvidia_smi_path,
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[nvidia-smi] found but failed to run: {exc}")
        return

    if result.returncode != 0 or not result.stdout.strip():
        print("[nvidia-smi] present but reported no GPU / returned an error:")
        print(result.stderr.strip() or "(no stderr output)")
        return

    print("[nvidia-smi] NVIDIA GPU(s) detected:")
    for line in result.stdout.strip().splitlines():
        print(f"    {line.strip()}")


def check_torch_cuda_if_present() -> None:
    try:
        import torch
    except ImportError:
        print("[torch] not installed in this environment — skipping framework-level CUDA check.")
        print("        This is expected in Phase 2: no ML framework has been chosen/installed yet.")
        print("        Once a framework is installed (a later, M1/M2-owned phase), re-run this")
        print("        script to also see framework-level CUDA availability.")
        return

    try:
        available = torch.cuda.is_available()
    except Exception as exc:  # pragma: no cover - defensive, torch internals vary by build
        print(f"[torch] installed but CUDA check raised an error: {exc}")
        return

    if available:
        device_name = torch.cuda.get_device_name(0)
        print(f"[torch] CUDA available. Device 0: {device_name}")
    else:
        print("[torch] installed, but CUDA is NOT available to it — will run on CPU.")


def main() -> int:
    print("Project SRT — GPU/CPU diagnostic (Rule 19)")
    print("=" * 60)
    check_nvidia_smi()
    print("-" * 60)
    check_torch_cuda_if_present()
    print("=" * 60)
    print("CPU fallback: the environment remains usable regardless of the above result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
