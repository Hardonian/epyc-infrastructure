#!/usr/bin/env python3
"""
VRAM budget checker for EPYC GPU lanes.

Validates whether a requested model/workload can fit on a target GPU,
checks current VRAM usage, and enforces admission control rules.

Usage:
    python3 scripts/validate/vram-budget-checker.py [--gpu all|0|1|2] [--model MODEL_NAME] [--context CTX] [--parallel N]

Exit codes:
    0 = admitted
    1 = rejected (budget exceeded)
    2 = error (invalid args, missing dependency)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GPU_IDENTITY_PATH = REPO_ROOT / "configs" / "hardware" / "gpu-identity.json"
SERVING_PROFILES_PATH = REPO_ROOT / "configs" / "serving-profiles" / "ollama-lanes.yaml"

# Approximate VRAM requirements for common quantizations (GB)
MODEL_VRAM_ESTIMATES = {
    "3b": {"q4": 2.5, "q6": 3.5, "q8": 4.5},
    "7b": {"q4": 5.0, "q6": 7.0, "q8": 9.0},
    "8b": {"q4": 6.0, "q6": 8.0, "q8": 11.0},
    "14b": {"q4": 10.0, "q6": 14.0, "q8": 18.0},
    "27b": {"q4": 18.0, "q6": 24.0, "q8": 30.0},
    "32b": {"q4": 21.0, "q6": 28.0, "q8": 36.0},
}

# KV cache overhead per token (approximate, in MB)
KV_CACHE_OVERHEAD_PER_TOKEN_MB = {
    "3b": 0.5,
    "7b": 1.0,
    "8b": 1.2,
    "14b": 2.0,
    "27b": 4.0,
    "32b": 5.0,
}


def run_cmd(cmd: str) -> str:
    """Run a shell command and return stdout."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: command failed: {cmd}\n{e.stderr}", file=sys.stderr)
        sys.exit(2)


def get_gpu_identity():
    """Load GPU identity config."""
    try:
        with open(GPU_IDENTITY_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: cannot load {GPU_IDENTITY_PATH}: {e}", file=sys.stderr)
        sys.exit(2)


def get_live_vram() -> dict:
    """Query live VRAM usage via nvidia-smi."""
    output = run_cmd(
        "nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader,nounits"
    )
    gpus = {}
    for line in output.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            idx = int(parts[0])
            used = int(parts[1])
            total = int(parts[2])
            gpus[idx] = {"used_mib": used, "total_mib": total, "free_mib": total - used}
    return gpus


def estimate_model_vram(model_name: str, context: int, quantization: str = "q4") -> float:
    """Estimate VRAM requirement in MB for a given model."""
    model_lower = model_name.lower()
    # Extract size hint from model name
    size_gb = None
    for key in ["32b", "27b", "14b", "8b", "7b", "3b"]:
        if key in model_lower:
            size_gb = MODEL_VRAM_ESTIMATES.get(key, {}).get(quantization, None)
            break

    if size_gb is None:
        # Default to conservative estimate for unknown models
        size_gb = 10.0

    # Convert GB to MB
    model_vram_mb = size_gb * 1024

    # Add KV cache overhead (rough: 2 bytes per token per layer, simplified)
    kv_overhead_mb = KV_CACHE_OVERHEAD_PER_TOKEN_MB.get("14b", 2.0) * context / 1000

    # Add runtime overhead (~1-2 GB)
    runtime_overhead_mb = 1024

    total_mb = model_vram_mb + kv_overhead_mb + runtime_overhead_mb
    return total_mb


def check_admission(gpu_index: int, model_vram_mb: float, parallel: int = 1) -> dict:
    """Check if a workload can be admitted to a GPU."""
    identity = get_gpu_identity()
    live = get_live_vram()

    gpu = identity["gpus"][gpu_index]
    live_gpu = live.get(gpu_index, {})

    total_mib = gpu["vram_total_mib"]
    used_mib = live_gpu.get("used_mib", 0)
    free_mib = total_mib - used_mib

    required_mib = model_vram_mb * parallel

    result = {
        "gpu_index": gpu_index,
        "gpu_name": gpu["name"],
        "total_mib": total_mib,
        "used_mib": used_mib,
        "free_mib": free_mib,
        "required_mib": required_mib,
        "parallel": parallel,
        "admitted": free_mib >= required_mib,
        "headroom_mib": free_mib - required_mib,
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="VRAM budget checker")
    parser.add_argument("--gpu", default="all", help="GPU index or 'all'")
    parser.add_argument("--model", required=True, help="Model name (e.g. qwen3.5:27b)")
    parser.add_argument("--context", type=int, default=4096, help="Context length")
    parser.add_argument("--parallel", type=int, default=1, help="Parallel requests")
    parser.add_argument("--quantization", default="q4", help="Quantization: q4, q6, q8")
    args = parser.parse_args()

    identity = get_gpu_identity()
    gpu_count = len(identity["gpus"])

    if args.gpu == "all":
        indices = list(range(gpu_count))
    else:
        try:
            indices = [int(args.gpu)]
        except ValueError:
            print(f"ERROR: invalid --gpu value: {args.gpu}", file=sys.stderr)
            sys.exit(2)

    model_vram_mb = estimate_model_vram(args.model, args.context, args.quantization)
    print(f"Estimated VRAM for {args.model} ({args.quantization}, ctx={args.context}): {model_vram_mb:.0f} MB")
    print(f"Parallel requests: {args.parallel}")
    print()

    admitted_any = False
    results = []
    for idx in indices:
        result = check_admission(idx, model_vram_mb, args.parallel)
        results.append(result)
        status = "ADMITTED" if result["admitted"] else "REJECTED"
        print(
            f"GPU {idx} ({result['gpu_name']}): {status} "
            f"| free={result['free_mib']} MB | need={result['required_mib']:.0f} MB "
            f"| headroom={result['headroom_mib']:.0f} MB"
        )
        if result["admitted"]:
            admitted_any = True

    print()
    if admitted_any:
        print("RESULT: admitted")
        sys.exit(0)
    else:
        print("RESULT: rejected")
        sys.exit(1)


if __name__ == "__main__":
    main()
