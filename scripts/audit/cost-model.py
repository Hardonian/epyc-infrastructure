#!/usr/bin/env python3
"""
Cost model estimator for EPYC GPU lanes.

Estimates $/1M tokens for a given model + GPU + workload using
approximate power draw, VRAM footprint, and local electricity rate.

Usage:
    python3 scripts/audit/cost-model.py [--gpu 0|1|2] [--model MODEL] [--context CTX] [--requests N] [--kwh-rate RATE]

Exit codes:
    0 = success
    2 = error
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GPU_IDENTITY_PATH = REPO_ROOT / "configs" / "hardware" / "gpu-identity.json"

# Defaults
DEFAULT_KWH_RATE = 0.12  # USD/kWh, adjust to local utility rate
HOST_POWER_IDLE_W = 120  # approximate EPYC host idle power (CPU + RAM + disks)
CPU_TDP_W = 280  # EPYC 7452 TDP; actual draw varies by load


def run_cmd(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: command failed: {cmd}\n{e.stderr}", file=sys.stderr)
        sys.exit(2)


def load_gpu_identity():
    try:
        with open(GPU_IDENTITY_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: cannot load {GPU_IDENTITY_PATH}: {e}", file=sys.stderr)
        sys.exit(2)


def get_live_power() -> dict:
    """Query live power draw via nvidia-smi."""
    output = run_cmd(
        "nvidia-smi --query-gpu=index,power.draw --format=csv,noheader,nounits"
    )
    gpus = {}
    for line in output.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            idx = int(parts[0])
            try:
                power_w = float(parts[1])
            except ValueError:
                power_w = None
            gpus[idx] = {"power_draw_w": power_w}
    return gpus


def estimate_cost(
    gpu_index: int,
    model_name: str,
    context: int,
    requests: int = 1000,
    kwh_rate: float = DEFAULT_KWH_RATE,
) -> dict:
    """Estimate cost per 1M generated tokens."""
    identity = load_gpu_identity()
    live = get_live_power()

    gpu = identity["gpus"][gpu_index]
    live_power = live.get(gpu_index, {}).get("power_draw_w")

    # Use measured power if available; otherwise fall back to identity/TDP heuristics
    if live_power is not None:
        total_system_w = HOST_POWER_IDLE_W + live_power
    else:
        total_system_w = HOST_POWER_IDLE_W + gpu.get("tdp_w", 250)

    # Convert to kW
    total_system_kw = total_system_w / 1000.0

    # Assume sustained workload duration proportional to context + generation
    # Very rough: 1 request = ~2 seconds of GPU-active time at this context
    seconds_per_request = max(1.0, context / 2048.0) * 2.0
    total_hours = (requests * seconds_per_request) / 3600.0

    energy_kwh = total_system_kw * total_hours
    cost_usd = energy_kwh * kwh_rate

    tokens = requests * context
    cost_per_1m_tokens = (cost_usd / tokens) * 1_000_000 if tokens > 0 else 0.0

    return {
        "gpu_index": gpu_index,
        "gpu_name": gpu["name"],
        "model_name": model_name,
        "context": context,
        "requests": requests,
        "kwh_rate_usd": kwh_rate,
        "total_system_w": total_system_w,
        "seconds_per_request": seconds_per_request,
        "total_hours": total_hours,
        "energy_kwh": energy_kwh,
        "cost_usd": cost_usd,
        "cost_per_1m_tokens_usd": cost_per_1m_tokens,
    }


def main():
    parser = argparse.ArgumentParser(description="EPYC GPU cost model estimator")
    parser.add_argument("--gpu", type=int, required=True, help="GPU index (0, 1, 2)")
    parser.add_argument("--model", required=True, help="Model name, e.g. qwen3.5:27b")
    parser.add_argument("--context", type=int, default=4096, help="Context length")
    parser.add_argument("--requests", type=int, default=1000, help="Request count for estimate")
    parser.add_argument("--kwh-rate", type=float, default=DEFAULT_KWH_RATE, help="USD per kWh")
    args = parser.parse_args()

    result = estimate_cost(
        gpu_index=args.gpu,
        model_name=args.model,
        context=args.context,
        requests=args.requests,
        kwh_rate=args.kwh_rate,
    )

    print(f"Model: {result['model_name']} | GPU: {result['gpu_name']} | ctx={result['context']}")
    print(f"Power estimate: {result['total_system_w']:.0f} W system ({result['seconds_per_request']:.1f}s/request)")
    print(f"Energy for {result['requests']} requests: {result['energy_kwh']:.4f} kWh @ ${result['kwh_rate_usd']}/kWh")
    print(f"Total cost: ${result['cost_usd']:.4f}")
    print(f"Cost per 1M tokens: ${result['cost_per_1m_tokens_usd']:.2f}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
