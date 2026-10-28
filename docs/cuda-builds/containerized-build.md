# Containerized CUDA Build Procedure

## Problem

The host's newer GCC and glibc environment causes compilation and link failures for
CUDA 12.6 workloads built directly on the host.

## Solution

Compile inside a compatible CUDA 12.6 / Ubuntu 24.04 development container.

### Verified Container Image

```
nvidia/cuda:12.6.3-devel-ubuntu24.04
```

### Build Steps (pattern)

```bash
# 1. Mount source tree read-only and build artifacts writable
docker run --rm --gpus all \
  -v /path/to/llama.cpp:/work:ro \
  -v /path/to/build-out:/build \
  nvidia/cuda:12.6.3-devel-ubuntu24.04 \
  /bin/bash -c "
    cd /work &&
    cmake -B /build -DCMAKE_BUILD_TYPE=Release \
      -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=70 \
      -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF &&
    cmake --build /build -j\$(nproc)
  "
```

### Architecture-Specific Builds

| GPU | SM | CMAKE_CUDA_ARCHITECTURES |
|---|---|---|
| V100 | 7.0 | 70 |
| P40 | 6.1 | 61 |
| RTX 3060 | 8.6 | 86 |

### Driver Stub Libraries

The container uses CUDA driver stub libraries only for linking. The actual NVIDIA
driver is injected at runtime via Docker `--gpus` flag. Do not install drivers
inside the container.

### Networking

Some build steps require network access (dependency download, git submodules).
Ensure the container has network access during initial configuration.

### Separate Inference Engines

Build separate binaries per GPU architecture. Do not ship a single binary and
rely on runtime JIT from mismatched PTX.

## Provenance

Source trees:
- `llama.cpp` upstream (master, ggml-org)
- `llama-phase8-pr25334-clean-v3` (Qwen3.5 fix applied)

Build outputs:
- `build-phase9-p40-sm61-headless/bin/llama-server`
- `build-v100-cuda12-container/bin/llama-server`

## Lessons Learned

- Host glibc version mismatch causes silent link failures.
- Containerized build isolates toolchain and guarantees reproducibility.
- Always verify the binary runs on the target GPU before declaring success.
- `--rm` containers delete themselves on exit; preserve logs and build artifacts
  on mounted volumes.
