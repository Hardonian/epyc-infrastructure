"""Integration tests for the EPYC XLAxiom adapter."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the adapter package is importable from the test location.
XLAXIOM_SRC = Path("/home/scott/XLAxiom/src")
if str(XLAXIOM_SRC) not in sys.path:
    sys.path.insert(0, str(XLAXIOM_SRC))

from xlaxiom_adapter.epyc_router import (  # noqa: E402
    _load_gpu_identity,
    _load_routing_policies,
    env_for_route,
    select_device_for_task,
)


def test_gpu_identity_loads():
    gpus = _load_gpu_identity()
    assert len(gpus) == 3, f"expected 3 GPUs, got {len(gpus)}"
    ordinals = {g.get("cuda_ordinal") for g in gpus}
    assert ordinals == {0, 1, 2}, f"unexpected ordinals: {ordinals}"


def test_routing_policies_load():
    policies = _load_routing_policies()
    assert "model_to_gpu_rules" in policies
    assert "latency_vs_throughput" in policies


def test_vision_task_prefers_3060():
    route = select_device_for_task("vision", "qwen3-vl:latest")
    assert route.cuda_ordinal == 1, f"vision should prefer RTX 3060 (ord 1), got {route.cuda_ordinal}"
    assert "RTX 3060" in route.gpu_name


def test_batch_14b_prefers_v100():
    route = select_device_for_task("batch", "qwen2.5:14b")
    assert route.cuda_ordinal == 0, f"14b batch should prefer V100 (ord 0), got {route.cuda_ordinal}"


def test_tensorrt_fallback_prefers_3060():
    route = select_device_for_task("tensorrt", "qwen3.5:9b")
    assert route.cuda_ordinal == 1, f"tensorrt fallback should be RTX 3060 (ord 1), got {route.cuda_ordinal}"


def test_env_pins_cuda_visible_devices():
    route = select_device_for_task("interactive", "qwen3.5:27b")
    env = env_for_route(route)
    assert env["CUDA_VISIBLE_DEVICES"] == str(route.cuda_ordinal)
    assert env["XLA_PYTHON_CLIENT_PREALLOCATE"] == "false"


if __name__ == "__main__":
    tests = [
        test_gpu_identity_loads,
        test_routing_policies_load,
        test_vision_task_prefers_3060,
        test_batch_14b_prefers_v100,
        test_tensorrt_fallback_prefers_3060,
        test_env_pins_cuda_visible_devices,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {e}")
            failed += 1

    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
