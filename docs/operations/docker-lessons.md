# Docker Execution Lessons

## Verified Container Image

```
nvidia/cuda:12.6.3-devel-ubuntu24.04
```

## Lessons Learned (from Phases 1-11)

### GPU Ordinal Assumptions
CUDA runtime ordinal does NOT match nvidia-smi index:
- Runtime 0 = V100 (nvidia-smi 0)
- Runtime 1 = RTX 3060 (nvidia-smi 2)
- Runtime 2 = P40 (nvidia-smi 1)

Always select GPUs by name or UUID in Docker `--gpus` flags, not by ordinal.

### Container Networking
- Use `--network host` for low-latency inference serving.
- Container-local networking causes port-publish mismatches.
- Verify with `ss -tlnp` inside the container if networking is suspect.

### Published Port and Loopback Binding
- llama-server binds to `127.0.0.1` inside the container.
- With `--network host`, this binds to the host loopback.
- External access requires host-side forwarding (Caddy or cloudflared).

### Shared Library Mount Paths
- Do not mount host `/usr/local/cuda/lib64` into the container.
- The container has its own matching CUDA toolkit.
- Host libcuda shadows the container's driver stub and causes link failures.

### Premature Container Deletion
- `--rm` deletes the container on exit.
- Preserve logs by mounting a volume or using `--log-driver journald`.
- A crashed container with `--rm` destroys diagnostic evidence.

### Missing Server Initialization Log Markers
- llama-server logs `HTTP server started` on success.
- Absence of this marker means the server failed to bind or initialize.
- Check container logs before probing ports.

### GPU Identity Failures
- A container may start but not see the expected GPU if `--gpus` is omitted.
- Verify with `nvidia-smi` inside the container or `nvidia-smi` on host.
- A running container with 0% GPU utilization may not have the GPU attached.

### Unbounded Retry/Soak Loops
- Soak tests should have bounded duration and request count.
- Unbounded loops consume GPU hours and mask transient failures.
- Record start/end timestamps and request counts for every soak.

### VRAM Competition
- Multiple containers on the same GPU fight for VRAM.
- Use isolated lanes (one container per GPU) for production serving.
- Check VRAM with `nvidia-smi --query-compute-apps` before launching new workloads.

## Regression Tests

1. Container starts and logs `HTTP server started`.
2. `nvidia-smi` shows VRAM used on the expected GPU.
3. Health endpoint returns 200 within 120s of container start.
4. Cold-load timeout is >120s for 20GB+ models.
5. No cross-GPU VRAM usage from a single-lane container.
