# Rollback and Recovery Procedures

## Quick Rollback for Phase 11 Services

```bash
python3 /home/scott/Downloads/epyc-tesla-phase11-resilient.py --rollback
```

This stops/removes:
- epyc-tesla-p40-27b.service
- epyc-tesla-v100-3b.service
- epyc-tesla-canary-router.service
- epyc-tesla-health-monitor.service

It does NOT stop or change Ollama.

## Configuration Drift Recovery

If a systemd unit's effective config diverges from the known-good state:
1. Check drop-in directories: `ls ~/.config/systemd/user/<unit>.service.d/`
2. Read the last-alphabetical file (it wins by precedence).
3. Restore the known-good drop-in or remove contradictory stale files.
4. Run `systemctl --user daemon-reload && systemctl --user restart <unit>`

## GPU Lane Recovery

If an Ollama lane loses its GPU or loads the wrong model:
1. Verify CUDA_VISIBLE_DEVICES matches intended GPU.
2. Check `nvidia-smi --query-compute-apps` for VRAM attribution.
3. Force-unload with `keep_alive=0` (graceful), NOT kill.
4. Verify with `nvidia-smi` VRAM drop.

## Docker Container Recovery

If a llama.cpp container crashes or fails to start:
1. Check logs: `journalctl --user -u <container-name> -n 50`
2. Verify GPU attachment: `docker inspect <container> | jq '.[0].HostConfig.DeviceRequests'`
3. Verify port binding: `ss -tlnp | grep <port>`
4. Cold-load timeout: allow 120s+ for 20GB+ models.
5. Recreate with same command if configuration is unchanged.

## Boot Validation

After kernel/driver updates:
1. Verify `gpu-unlock` module loaded: `dmesg | grep gpu_unlock`
2. Verify DKMS status: `dkms status gpu-unlock && dkms status nvidia`
3. Verify all expected kernel symlinks exist.
4. Run RTX 3060 audit script.
5. Verify Ollama lanes start and bind to correct GPUs.

## Backup Restore

See `/home/scott/BACKUP_RESTORE.md` for OS and NVMe restore procedures.
Backup status: `cat ~/.hermes/state/backup-last.json`.
