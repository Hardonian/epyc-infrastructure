# EPYC AI Infrastructure Knowledge Repository

## Purpose

Permanent, version-controlled record of the EPYC Ubuntu research host's hardware,
GPU optimization history, benchmark evidence, build configurations, and operational
procedures. This repo exists to prevent knowledge loss across sessions, agents, and
hardware upgrades.

## Current Hardware Inventory (verified 2026-10-27)

| Component | Configuration |
|---|---|
| Host | AMD EPYC 7452 |
| RAM | ~168 GiB ECC |
| OS | Ubuntu Linux 7.0.0-38-generic |
| Root LV | 466G (72% used, 128G free) |
| GPU 0 | Tesla V100-SXM2-16GB (SM 7.0, 16GB VRAM) |
| GPU 1 | Tesla P40 (SM 6.1, 24GB VRAM) |
| GPU 2 | RTX 3060 (SM 8.6, 12GB VRAM) |
| NVIDIA driver | 580.x (host), 580.196.07 (container) |
| CUDA runtime | 12.6.3 (container build env) |
| Ollama | 0.32.9 (local install) |
| Hermes Agent | v0.22.5 |

### GPU Identity Mapping (critical)

CUDA ordinal does NOT match nvidia-smi index:
- CUDA ord 0 = V100 (nvidia-smi idx 0)
- CUDA ord 1 = RTX 3060 (nvidia-smi idx 2)
- CUDA ord 2 = P40 (nvidia-smi idx 1)

Always match by name/UUID, never by ordinal alone.

## Architecture Overview

```
EPYC Host
├── 3x NVIDIA GPUs (isolated lanes)
├── Ollama 0.32.9 (3 lanes + router)
│   ├── Lane v100  :11434 → GPU 0 (V100)
│   ├── Lane p40   :11435 → GPU 1 (P40)
│   ├── Lane 3060  :11436 → GPU 2 (RTX 3060)
│   └── Router     :11438 → all GPUs
├── llama.cpp servers (Docker, CUDA 12.6.3 container)
│   ├── P40 27B    :12035 (SM61 build)
│   └── V100 3B    :12034 (SM70 build)
├── Local services (systemd user units)
│   ├── storefront :8020
│   ├── hardonia-portal :8090
│   ├── hardonia-compute-api :8050
│   ├── ai-lab-audit-api :8011
│   ├── checkout-api :8012
│   ├── command-center :8000
│   └── ollama-router :11438
└── Cloudflare tunnel (system-level unit)
    └── ai-lab-epyc → public domains
```

## Verified Performance Highlights

All measurements are workload-specific. Do not compare across unlike configurations.

### P40 — Qwen3.5 27B (SM61, flash attention enabled)
| Context | Concurrent | Aggregate throughput |
|---|---:|
| 4K | 1 | 10.51 tok/s |
| 4K | 2 | 16.80 tok/s |
| 8K | 1 | 10.50 tok/s |
| 8K | 2 | 16.79 tok/s |
| 16K | 1 | 10.54 tok/s |
| 16K | 2 | 16.82 tok/s |
| Soak (various) | 2 | 17.30–17.61 tok/s |

### V100 — Qwen2.5 3B (SM70, flash attention enabled)
| Concurrent | Aggregate throughput |
|---|---:|
| 1 | 188.37 tok/s |
| 2 | 299.70 tok/s |
| 4 | 436.53 tok/s |

### Historical decode results (different benchmark configs)
| GPU | Model | Throughput |
|---|---|---:|
| P40 | 8B | ~39 tok/s |
| P40 | 14B | ~21 tok/s |
| P40 | Qwen3.5 27B | ~11 tok/s |
| V100 | 8B | ~119 tok/s |
| V100 | 14B | ~66 tok/s |

See `benchmarks/raw/` for original artifacts and provenance.

## Inference and Service Layout

- Each GPU runs exactly one Ollama instance (isolated lanes).
- Router at :11438 selects by VRAM fit, model size, and modality.
- Large models (27B+) default to P40 (24GB).
- Fast small models default to V100 (16GB, high SM count).
- RTX 3060 handles vision models and interactive small models.
- llama.cpp Docker servers provide dedicated low-latency endpoints for specific models.
- All Ollama instances set `OLLAMA_VULKAN=false` to prevent cross-GPU discovery.

## Build Reproducibility

CUDA 12.6 workloads compile inside `nvidia/cuda:12.6.3-devel-ubuntu24.04` containers.
Host GCC/glibc causes link failures with newer toolchains; containerized build uses
matching Ubuntu 24.04 toolchain. GPU driver is injected at runtime via Docker
`--gpus` flag; container only needs stub libraries for linking.

Separate binaries per GPU architecture:
- SM61 (P40): `build-phase9-p40-sm61-headless/bin/llama-server`
- SM70 (V100): `build-v100-cuda12-container/bin/llama-server`

Source provenance: `llama-phase8-pr25334-clean-v3` (commit `e4ee2d2`), based on
llama.cpp upstream with Qwen3.5 RoPE fix applied.

## Optimization Decisions

| Decision | Outcome | Evidence |
|---|---|---|
| Flash attention on P40 3B | Disabled (regression) | `benchmarks/raw/` |
| Flash attention on P40 8B/14B | Enabled (gain) | `benchmarks/raw/` |
| Flash attention on V100 | Enabled (gain) | `benchmarks/raw/` |
| Forced MMQ on V100 | Mixed/negative | Preserved as negative result |
| Qwen3.5 RoPE 3-section GGUF | Fixed in llama.cpp fork | `docs/optimization-history/qwen35-rope-fix.md` |
| Ollama Vulkan bypass | Blocked with env var | `docs/operations/vulkan-isolation.md` |

## Reliability and Recovery

- P40 service: model warm, context 8192, 2 parallel slots, endpoint :12035
- V100 service: model warm, context 4096, 4 parallel slots, endpoint :12034
- Rollback: `python3 /home/scott/Downloads/epyc-tesla-phase11-resilient.py --rollback`
- Boot validation: systemd user units with restart policies
- GPU identity: verified by UUID, not ordinal

## Benchmark Methodology

Benchmarks record:
- Timestamp, duration, CPU/GPU/memory state
- Model name, architecture, quantization, digest
- Backend, build commit, CUDA runtime/driver/kernel
- Prompt config, context capacity, actual prompt length
- Generated token count, flash attention, MMQ settings
- Concurrent requests, aggregate throughput, per-request latency
- Time to first token (when measured)
- Peak VRAM, GPU power, energy efficiency (when measured)
- Background workload interference
- Verification status and confidence level

Categories:
1. Verified results (controlled, matched conditions)
2. Observational metrics
3. Inferred performance
4. Untested hypotheses
5. Failed experiments

See `benchmarks/schemas/benchmark-schema.json` for the canonical format.

## Cost and Task-Selection Principles

- Cheapest suitable hardware that meets latency/quality constraints.
- Avoid GPU oversubscription; measure contention cost.
- Distinguish throughput optimization from latency optimization.
- Parallel execution requires task independence + resource availability + justified total completion time improvement.
- Local execution has non-zero cost: electricity, amortization, opportunity cost.

## Quickstart

```bash
# GPU topology
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader

# Ollama health
curl -s http://127.0.0.1:11438/health

# Per-lane status
for p in 11434 11435 11436; do echo ":$p"; curl -s http://127.0.0.1:$p/api/ps; done

# VRAM audit
nvidia-smi --query-compute-apps=pid,used_gpu_memory,gpu_name --format=csv,noheader

# Service health
for p in 8000 8020 8050 8011 8012 8085 8090 11438 12034 12035; do
  printf '%s ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:$p/" 2>/dev/null || echo 'nc'
done
```

## Known Limitations

- RTX 3060 Tensor Core unlock verified activated; throughput improvement not yet independently quantified with controlled benchmark.
- Mem0 backend currently failing (API key invalid) — Hermes persistent memory degraded.
- No cloud offsite backup (only cross-drive rsync).
- JAX CUDA 13 works only on RTX 3060; V100/P40 must use cuda12 wheel.
- Only RTX 3060 (CC 8.6) supports Dynamo/NIM.
- Some historical benchmarks used different methodologies; cross-config comparison is unreliable.

## Related Projects

| Project | Remote | Status | Integration Notes |
|---|---|---|---|
| argon-engine | `Hardonian/argon-engine` (public) | builds clean, Ollama integration verified | Rust workspace with Vulkan/Metal/ROCm/CPU backends; local-first Ollama client confirmed healthy |
| deepinfer-serving | `Hardonian/deepinfer-serving` (private) | 0.3.0 CPU serving candidate, smoke tests pass | fake-worker mode operational; real inference gated behind hardware evidence |

## License

See LICENSE file. Infrastructure documentation is proprietary unless otherwise noted.
llama.cpp source trees are under their respective licenses (see `LICENSE` in each source tree).
