# Resilience and Production Operations

## Persistent Inference Configuration

### P40 Service
- Model: Qwen3.5 27B
- Context: 8192
- Parallel slots: 2
- Local endpoint: 127.0.0.1:12035
- Container: `epyc-tesla-p40-27b` (Docker, host network, GPU UUID match)

### V100 Service
- Model: Qwen2.5 3B
- Context: 4096
- Parallel slots: 4
- Local endpoint: 127.0.0.1:12034
- Container: `epyc-tesla-v100-3b` (Docker, host network, GPU UUID match)

### Canary Router
- Endpoint: 127.0.0.1:12080
- Purpose: Opt-in canary routing for new models/configurations

## Deployment Verification

The deployment successfully completed more than 170 short soak requests during commissioning.

## Systemd Service Health

Running services (verified 2026-10-27):
- ai-lab-audit-api.service
- ai-lab-command-center.service
- comfyui.service
- epyc-portal.service
- epyc-tesla-canary-router.service
- epyc-tesla-health-monitor.service
- epyc-tesla-p40-27b.service
- epyc-tesla-v100-3b.service
- gpu-exporter.service
- hardonia-compute-api.service
- lab-dashboard.service
- lead-response-agent.service
- litellm-host.service
- ollama-3060.service
- ollama-default.service
- ollama-p40.service
- ollama-router.service
- vramd.service

Active timers:
- gpu-idle-seller.timer
- ai-lab-watchdog.timer
- epyc-tesla-resilience.timer
- ollama-health.timer
- gpu-thermal-watchdog.timer
- ollama-router-watchdog.timer

## Rollback

```bash
python3 /home/scott/Downloads/epyc-tesla-phase11-resilient.py --rollback
```

This only stops/removes `epyc-tesla-{p40-27b,v100-3b,canary-router,health-monitor}.service`.
It does not change or stop Ollama.

## Resilience Improvements Needed

- Boot validation script (non-destructive, post-reboot)
- Driver and CUDA compatibility checks before builds
- Configuration drift reporting
- Proven-good configuration preservation
- Repeated-failure cooldowns
- Post-update regression detection

Do not automatically promote new benchmarks to production without verifying:
- Correctness
- Reliability
- Memory headroom
- Latency requirements
