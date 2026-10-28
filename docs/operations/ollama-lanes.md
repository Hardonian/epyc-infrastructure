# Ollama GPU Lane Configuration

## Live Lanes (verified 2026-10-27)

| Lane | Service | Port | GPU | Keep-Alive | Max Loaded |
|---|---|---|---|---|---|
| v100 | ollama-default.service | 11434 | V100 (ord 0) | 1800s | 2 |
| p40 | ollama-p40.service | 11435 | P40 (ord 1 via PCI) | 7200s | 4 |
| 3060 | ollama-3060.service | 11436 | RTX 3060 (ord 2) | 1800s | 4 |
| router | ollama-router.service | 11438 | ALL | smart | — |

## Environment Variables (effective)

All lanes:
- `OLLAMA_VULKAN=false` (prevents Vulkan fallback bypassing CUDA_VISIBLE_DEVICES)
- `CUDA_DEVICE_ORDER=PCI_BUS_ID`
- `OLLAMA_MODELS=/mnt/ai-storage/ollama-models`

V100 lane:
- `CUDA_VISIBLE_DEVICES=0`
- `OLLAMA_KEEP_ALIVE=1800`
- `OLLAMA_MAX_LOADED_MODELS=2`

P40 lane:
- `CUDA_VISIBLE_DEVICES=1`
- `OLLAMA_KEEP_ALIVE=7200`
- `OLLAMA_FLASH_ATTENTION=1`
- `OLLAMA_KV_CACHE_TYPE=q4_0`
- `OLLAMA_NUM_PARALLEL=4`
- `OLLAMA_MAX_LOADED_MODELS=4`
- `OLLAMA_LIBRARY_PATH=/home/scott/.local/ollama-0.32.9/lib/ollama`

3060 lane:
- `CUDA_VISIBLE_DEVICES=2`
- `OLLAMA_KEEP_ALIVE=1800`
- `OLLAMA_FLASH_ATTENTION=1`
- `OLLAMA_KV_CACHE_TYPE=q4_0`
- `OLLAMA_NUM_PARALLEL=4`
- `OLLAMA_MAX_LOADED_MODELS=4`
- `OLLAMA_LIBRARY_PATH=/home/scott/.local/ollama-0.32.9/lib/ollama`

## Vulkan Isolation Guard

Ollama 0.30.8+ uses Vulkan fallback to discover GPUs, bypassing `CUDA_VISIBLE_DEVICES`.
Without `OLLAMA_VULKAN=false`, each instance sees all GPUs and causes cross-GPU
model loading and memory contention.

Verification:
```bash
journalctl --user -u ollama-p40 --since "5 min ago" | grep -i vulkan  # should be empty
nvidia-smi --query-compute-apps=gpu_name,process_name,used_memory --format=csv,noheader
```

## Router Health

Use `/health` for JSON, not `/status` (which returns HTML):
```bash
curl -s http://127.0.0.1:11438/health
```

## Model Routing Tree

```
Router :11438
  ├─ Vision (qwen3-vl, llava)? → GPU 2 (3060)
  ├─ >= 20B?
  │   ├─ Q4 quant? → GPU 1 (P40, 24GB)
  │   └─ Q6+? → GPU 0 (V100, 16GB)
  ├─ 7B-14B? → GPU 0 (speed) or GPU 1 (context)
  ├─ < 7B? → GPU 2 (interactive) or GPU 0 (batch)
  └─ Embedding? → GPU 2 (always resident, tiny)
```

## Retired Lanes

`ollama-v100.service` (:11437) is RETIRED. Do not restart, re-enable, probe, or
count it. The router's "v100" lane name intentionally points at :11434.
