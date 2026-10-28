# Architecture Decision Records

## ADR-001: GPU Lane Isolation via Separate Ollama Instances

**Date:** 2026-09
**Status:** Accepted

**Context:** Multiple GPUs with different capabilities and VRAM sizes. Single Ollama instance would pool GPUs transparently but could load a 27B model on the 16GB V100.

**Decision:** Run one Ollama instance per physical GPU, with a router selecting by VRAM fit.

**Consequences:** More services to manage, but deterministic placement and no VRAM surprises.

## ADR-002: Containerized CUDA Builds

**Date:** 2026-09
**Status:** Accepted

**Context:** Host GCC/glibc environment caused CUDA 12.6 link failures.

**Decision:** Compile inside `nvidia/cuda:12.6.3-devel-ubuntu24.04` containers. Inject host driver at runtime.

**Consequences:** Build reproducibility, isolated toolchain, slightly more complex build invocation.

## ADR-003: Vulkan Isolation via Environment Variable

**Date:** 2026-10
**Status:** Accepted

**Context:** Ollama 0.30.8+ Vulkan fallback bypasses `CUDA_VISIBLE_DEVICES`, causing cross-GPU model loading.

**Decision:** Set `OLLAMA_VULKAN=false` on all Ollama lanes.

**Consequences:** Requires environment variable enforcement in systemd drop-ins. Must re-apply after Ollama upgrades.

## ADR-004: Qwen3.5 Fork with RoPE Fix

**Date:** 2026-07
**Status:** Accepted

**Context:** Qwen3.5 GGUF exports had 3 RoPE sections; upstream llama.cpp expected 4.

**Decision:** Use private fork `llama-phase8-pr25334-clean-v3` (commit e4ee2d2) with variable-length RoPE section handling.

**Consequences:** Diverges from upstream. Must track upstream for merge of fix.

## ADR-005: RTX 3060 GPU Unlock for Tensor Cores

**Date:** 2026-10
**Status:** Accepted (activation verified, throughput improvement unmeasured)

**Context:** RTX 3060 Ampere GPU has firmware-level Tensor Core unlock available.

**Decision:** Enable unlock via gpu-unlock DKMS module, verified boot sequence, and recurring audit timer.

**Consequences:** Kernel module must be rebuilt on kernel updates. Theoretical speedup not yet independently benchmarked.

## ADR-006: Router Health Endpoint Selection

**Date:** 2026-10
**Status:** Accepted

**Context:** Router `/status` returns HTML; `/health` returns JSON.

**Decision:** Use `/health` for machine-readable health checks. Use `/api/tags` for model listings.

**Consequences:** Scripts that probe `/status` for JSON will fail.
