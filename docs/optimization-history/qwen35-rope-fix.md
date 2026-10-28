# Qwen3.5 RoPE Compatibility Fix

## Problem

Qwen3.5 GGUF exports from Ollama stored RoPE dimension metadata with **3 sections**
instead of the 4 sections expected by the llama.cpp loader at the time.

The older loader path called `ml.get_arr(LLM_KV_ROPE_DIMENSION_SECTIONS, ...)` without
length tolerance. When the GGUF contained only 3 entries, the load failed or produced
incorrect RoPE configuration, preventing Qwen3.5 models from running.

## Solution

In `src/models/qwen35.cpp` (and `qwen35moe.cpp`), the fix:

1. Zero-fills the rope_sections array first.
2. Calls `ml.get_arr(...)` with the `allow_variable_length` flag set to `true`.

```cpp
// some GGUFs (e.g. Ollama exports) store 3 rope sections instead of 4;
// accept either length and leave trailing sections zeroed
hparams.rope_sections.fill(0);
ml.get_arr(LLM_KV_ROPE_DIMENSION_SECTIONS, hparams.rope_sections, true);
```

This accepts either 3 or 4 sections and leaves trailing entries zeroed, which is the
correct behavior for models that do not use all four RoPE dimension groups.

## Provenance

| Field | Value |
|---|---|
| Source tree | `llama-phase8-pr25334-clean-v3` |
| Commit | `e4ee2d21a8ceae24aecdc7c3a229a48ad3b34ee5` |
| Author | Saurav Sharma |
| Date | 2026-07-05 |
| Message | `fix: load qwen35 Ollama GGUF exports` |
| Upstream llama.cpp | `ggml-org/llama.cpp` master at time of fork |

## Upstream Status

This fix is in a private fork (`llama-phase8-pr25334-clean-v3`). It may or may not
have been merged upstream since the fork date. Before relying on this fix in new
builds, check whether upstream llama.cpp now contains the same `allow_variable_length`
handling for `LLM_KV_ROPE_DIMENSION_SECTIONS`.

## Build Configuration

The working P40 build disables the optional embedded llama.cpp web UI to avoid an
unrelated `loading.html` asset failure.

Build artifacts:
- `build-phase9-p40-sm61-headless/bin/llama-server` (SM61)
- `build-v100-cuda12-container/bin/llama-server` (SM70)

Build environment: `nvidia/cuda:12.6.3-devel-ubuntu24.04` container, host driver
injected at runtime via `--gpus`.

## Negative Results Preserved

Experimental forced MMQ builds did not consistently outperform default kernels.
One V100 configuration exhibited substantial prefill regression. Do not promote
MMQ without new controlled benchmark evidence.

## Flash Attention

Flash attention benefit depends on GPU architecture, model size, and workload:
- P40 3B baseline: flash attention disabled (regression)
- P40 8B/14B: flash attention enabled (gain)
- V100: flash attention enabled (gain)

Do not generalize one setting across every model.
