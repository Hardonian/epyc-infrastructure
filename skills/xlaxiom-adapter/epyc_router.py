"""XLAxiom adapter for EPYC routing policy.

Reads EPYC infrastructure configs and returns a preferred CUDA device
for a given task/model so XLAxiom can pin work to the right GPU.

Usage:
    from xlaxiom_adapter.epyc_router import select_device_for_task
    device_info = select_device_for_task(task="interactive", model="qwen3.5:27b")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal

Task = Literal["interactive", "batch", "vision", "tensorrt", "comfyui", "default"]

# EPYC repo root: adapter resolves configs relative to this file.
ADAPTER_DIR = os.path.dirname(os.path.abspath(__file__))
EPYC_ROOT = os.path.normpath(
    os.path.join(os.path.realpath(ADAPTER_DIR), "..", "..")
)
GPU_IDENTITY_PATH = os.path.join(EPYC_ROOT, "configs", "hardware", "gpu-identity.json")
ROUTING_POLICIES_PATH = os.path.join(EPYC_ROOT, "configs", "routing-policies", "policies.json")
ROUTING_POLICIES_YAML_PATH = os.path.join(EPYC_ROOT, "configs", "routing-policies", "policies.yaml")

# Fallback routing when policy file is missing.
FALLBACK_ROUTE: dict[str, int] = {
    "interactive": 0,
    "batch": 0,
    "vision": 1,
    "tensorrt": 1,
    "comfyui": 1,
    "default": 0,
}


@dataclass(frozen=True)
class Route:
    task: Task
    cuda_ordinal: int
    gpu_name: str
    reason: str


def _load_gpu_identity() -> list[dict[str, Any]]:
    try:
        with open(GPU_IDENTITY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("gpus", [])
    except Exception:
        return []


def _load_routing_policies() -> dict[str, Any]:
    # Prefer JSON (no external dependency); fall back to YAML if available.
    for path in (ROUTING_POLICIES_PATH, ROUTING_POLICIES_YAML_PATH):
        if not os.path.exists(path):
            continue
        try:
            if path.endswith(".json"):
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            else:
                import yaml

                with open(path, "r", encoding="utf-8") as fh:
                    return yaml.safe_load(fh) or {}
        except Exception:
            continue
    return {}


def _match_model_to_gpu(model: str, policies: dict[str, Any]) -> tuple[int, str]:
    """Apply model_to_gpu_rules to pick a preferred GPU ordinal."""
    rules = policies.get("model_to_gpu_rules", [])
    model_lower = model.lower()

    # Extract size hint from model name (very rough)
    size_gb = None
    for key in ["32b", "27b", "14b", "8b", "7b", "3b"]:
        if key in model_lower:
            size_gb = {"32b": 32, "27b": 27, "14b": 14, "8b": 8, "7b": 7, "3b": 3}[key]
            break

    for rule in rules:
        match = rule.get("match", {})
        preferred = rule.get("prefer")
        if not preferred:
            continue

        # Check size_gb range
        size_rule = match.get("size_gb")
        if size_rule:
            if size_gb is None:
                # Unknown model size cannot satisfy a size constraint.
                continue
            if size_rule.startswith(">="):
                threshold = int(size_rule[2:])
                if size_gb < threshold:
                    continue
            elif size_rule.startswith("<"):
                threshold = int(size_rule[1:])
                if size_gb >= threshold:
                    continue
            elif "-" in size_rule:
                low, high = size_rule.split("-")
                if not (int(low) <= size_gb <= int(high)):
                    continue
            else:
                if size_gb != int(size_rule):
                    continue

        # Check quantization
        quantization = match.get("quantization")
        if quantization and quantization.upper() not in model_lower:
            continue

        # Check modality
        modality = match.get("modality")
        if modality == "vision" and "vision" not in model_lower and "vl" not in model_lower:
            continue

        # Check type
        m_type = match.get("type")
        if m_type == "embedding" and "embed" not in model_lower:
            continue

        return _gpu_name_to_ordinal(str(preferred)), f"policy:{rule.get('notes', preferred)}"

    return -1, "no-match"


def _gpu_name_to_ordinal(name: str) -> int:
    """Map a GPU name fragment from policy to CUDA ordinal."""
    gpus = _load_gpu_identity()
    name_lower = name.lower()
    for gpu in gpus:
        if name_lower in gpu.get("name", "").lower():
            return int(gpu.get("cuda_ordinal", 0))
    return 0


def select_device_for_task(
    task: Task = "default",
    model: str = "",
    context: int = 4096,
    parallel: int = 1,
) -> Route:
    """Return the preferred CUDA device for the requested task/model.

    This is intentionally read-only and never mutates host state.
    """
    gpus = _load_gpu_identity()
    policies = _load_routing_policies()

    # 1. Try model-based routing first.
    preferred_ordinal, reason = _match_model_to_gpu(model, policies)
    if preferred_ordinal >= 0:
        gpu = next((g for g in gpus if g.get("cuda_ordinal") == preferred_ordinal), None)
        if gpu:
            return Route(
                task=task,
                cuda_ordinal=int(preferred_ordinal),
                gpu_name=gpu.get("name", "unknown"),
                reason=reason,
            )

    # 2. Try task-based routing from latency_vs_throughput.
    latency_prefer = policies.get("latency_vs_throughput", {}).get("latency_sensitive_prefer")
    if task == "interactive" and latency_prefer:
        ordinal = _gpu_name_to_ordinal(str(latency_prefer))
        gpu = next((g for g in gpus if g.get("cuda_ordinal") == ordinal), None)
        if gpu:
            return Route(
                task=task,
                cuda_ordinal=ordinal,
                gpu_name=gpu.get("name", "unknown"),
                reason=f"policy:latency-sensitive={latency_prefer}",
            )

    throughput_rules = policies.get("latency_vs_throughput", {}).get("throughput_optimized", {})
    if task == "batch" and throughput_rules:
        # Pick first throughput rule as heuristic.
        preferred = list(throughput_rules.values())[0]
        ordinal = _gpu_name_to_ordinal(str(preferred))
        gpu = next((g for g in gpus if g.get("cuda_ordinal") == ordinal), None)
        if gpu:
            return Route(
                task=task,
                cuda_ordinal=ordinal,
                gpu_name=gpu.get("name", "unknown"),
                reason=f"policy:throughput={preferred}",
            )

    # 3. Fallback.
    preferred_ordinal = FALLBACK_ROUTE.get(task, 0)
    gpu = next((g for g in gpus if g.get("cuda_ordinal") == preferred_ordinal), None)
    if gpu is None and gpus:
        gpu = gpus[0]
        preferred_ordinal = gpu.get("cuda_ordinal", 0)
        reason = "identity-fallback"
    else:
        reason = f"fallback-{task}"

    return Route(
        task=task,
        cuda_ordinal=int(preferred_ordinal),
        gpu_name=gpu.get("name", "unknown") if gpu else "unknown",
        reason=reason,
    )


def env_for_route(route: Route) -> dict[str, str]:
    """Return environment overrides to pin JAX/XLA to the selected device."""
    return {
        "CUDA_VISIBLE_DEVICES": str(route.cuda_ordinal),
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
    }
