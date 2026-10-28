---
name: epyc-compute-intelligence
description: "Use when selecting GPU, routing inference workloads, estimating cost, or checking EPYC hardware state. Provides GPU topology, model routing, VRAM estimates, benchmark lookup, and cost modeling for the EPYC host."
version: 1.0.0
---

# EPYC Compute Intelligence

Load before any GPU selection, inference routing, cost estimation, or hardware
availability check on the EPYC fleet.

## When to use

- "Which GPU for this model?"
- "Can this job run in parallel?"
- "How much VRAM does this model need?"
- "What is the expected latency?"
- "Should this run on EPYC or HX370?"
- "What is the execution cost?"
- "Which previous experiments should not be repeated?"

## Hardware Topology (live source of truth)

Read from the knowledge repo's `configs/hardware/gpu-identity.json` or query live
state via:

```bash
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader
```

| Index | CUDA Ord | Name | VRAM | SM | Role |
|---|---|---|---|---|---|
| 0 | 0 | V100-SXM2-16GB | 16384 MiB | 7.0 | HEAVY: SDXL, large LLM, training |
| 1 | 2 | Tesla P40 | 23040 MiB | 6.1 | VISION: 32B models, large context |
| 2 | 1 | RTX 3060 | 12288 MiB | 8.6 | UI+LIGHT: ComfyUI, small/vision models |

**Critical:** CUDA ordinal does NOT match nvidia-smi index. Resolve by name/UUID.

## VRAM Estimation

Approximate VRAM requirements for common quantizations:

| Model Size | Q4_K_M | Q6_K | Q8_0 |
|---|---:|---:|---:|
| 3B | ~2.5 GB | ~3.5 GB | ~4.5 GB |
| 7B | ~5 GB | ~7 GB | ~9 GB |
| 8B | ~6 GB | ~8 GB | ~11 GB |
| 14B | ~10 GB | ~14 GB | ~18 GB |
| 27B | ~18 GB | ~24 GB | ~30 GB |
| 32B | ~21 GB | ~28 GB | ~36 GB |

Add 1-2 GB overhead for KV cache and runtime.

## Routing Rules

1. **>= 20B (Q4)** → P40 (24GB). Cold-load 45-120s.
2. **7B-14B** → V100 (speed) or P40 (context).
3. **< 7B** → V100 (batch) or 3060 (interactive).
4. **Vision** → 3060 (SM 8.6).
5. **Embedding** → 3060 (always resident, 274 MiB).
6. **JAX CUDA 13** → 3060 only. V100/P40 must use cuda12 wheel.

## Parallel Execution

Parallel is beneficial when:
- Tasks are independent
- Resource contention is acceptable
- Total completion time improves

V100 supports up to 4 parallel slots for 3B models.
P40 supports up to 4 parallel slots.
Do not parallelize solely because aggregate tok/s improves.

## Cost Model

```python
estimated_cost = (
    electricity_cost
    + hardware_amortization
    + storage_or_network_cost
    + contention_cost
)
```

Local hardware has non-zero cost:
- Electricity: measure with `nvidia-smi --query-gpu=power.draw`
- Amortization: configurable hardware acquisition cost
- Contention: opportunity cost of occupying a GPU

## Benchmark Lookup

Search `benchmarks/raw/` and `benchmarks/summaries/` for historical performance.
Use the schema in `benchmarks/schemas/benchmark-schema.json`.

Key reference measurements (do not compare across unlike configs):

| GPU | Model | Context | Concurrent | Throughput |
|---|---:|---|---:|---:|
| P40 | Qwen3.5 27B | 4K-16K | 2 | ~17 tok/s |
| V100 | Qwen2.5 3B | 4K | 4 | ~437 tok/s |
| V100 | Qwen2.5 3B | 4K | 1 | ~188 tok/s |

## Negative Results (do not repeat)

- Forced MMQ on V100: prefill regression observed. Do not promote without new evidence.
- Flash attention on P40 3B: disabled (regression). Enabled on 8B/14B (gain).

## Lightweight Tasks

For lightweight tasks, do not incur expensive planning overhead. Use direct routing:
- Small model inference → V100 or 3060
- Embeddings → 3060
- Vision → 3060

## Source of Truth Files

- Hardware: `configs/hardware/gpu-identity.json`
- Serving: `configs/serving-profiles/ollama-lanes.yaml`
- Routing: `configs/routing-policies/policies.yaml`
- Benchmarks: `benchmarks/raw/`, `benchmarks/summaries/`
- Schema: `benchmarks/schemas/benchmark-schema.json`
