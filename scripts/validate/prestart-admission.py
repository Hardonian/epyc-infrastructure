#!/usr/bin/env python3
"""
Pre-start validation hook for EPYC AI lanes.

Combines VRAM admission + cost-model checks before allowing a workload
to start. Intended to be called from systemd ExecStartPre, CI gates,
or router middleware.

Usage:
    python3 scripts/validate/prestart-admission.py --gpu 0 --model qwen2.5:14b --context 4096 --parallel 1

Exit codes:
    0 = admitted
    1 = rejected
    2 = error
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATE_DIR = REPO_ROOT / "scripts" / "validate"


def run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        print(f"ERROR: {cmd}\n{result.stderr}", file=sys.stderr)
        sys.exit(2)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="Pre-start admission gate")
    parser.add_argument("--gpu", required=True, help="GPU index")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--context", type=int, default=4096)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--quantization", default="q4")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--kwh-rate", type=float, default=0.12)
    args = parser.parse_args()

    vram_script = VALIDATE_DIR / "vram-budget-checker.py"
    cost_script = REPO_ROOT / "scripts" / "audit" / "cost-model.py"

    vram_cmd = (
        f"python3 {vram_script} --gpu {args.gpu} --model {args.model} "
        f"--context {args.context} --parallel {args.parallel} --quantization {args.quantization}"
    )
    cost_cmd = (
        f"python3 {cost_script} --gpu {args.gpu} --model {args.model} "
        f"--context {args.context} --requests {args.requests} --kwh-rate {args.kwh_rate}"
    )

    print(f"[admission] VRAM check: {vram_cmd}")
    vram_out = run(vram_cmd)

    print(f"[admission] Cost check: {cost_cmd}")
    cost_out = run(cost_cmd)

    admitted = "RESULT: admitted" in vram_out
    print()
    print("=== VRAM ===")
    print(vram_out)
    print("=== COST ===")
    print(cost_out)

    if not admitted:
        print()
        print("RESULT: rejected — VRAM budget exceeded")
        sys.exit(1)

    # Parse cost JSON tail
    try:
        cost_json = json.loads(cost_out.split("\n")[-1])
        cost_per_1m = cost_json.get("cost_per_1m_tokens_usd", 0.0)
        if cost_per_1m > 10.0:
            print()
            print(f"RESULT: rejected — cost per 1M tokens ${cost_per_1m:.2f} exceeds threshold")
            sys.exit(1)
    except Exception:
        pass

    print()
    print("RESULT: admitted")
    sys.exit(0)


if __name__ == "__main__":
    main()
