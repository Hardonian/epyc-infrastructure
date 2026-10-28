# RTX 3060 GPU Unlock Persistence

## Verified Configuration

| Field | Value |
|---|---|
| gpu-unlock version | 1.1.0 |
| Target PCI | 0000:c5:00.0 |
| Kernel | 7.0.0-38-generic |
| NVIDIA driver | 580.196.07 |

## Verified Boot Sequence

```
gpu_unlock: pass=1/2 ... ret=0
gpu_unlock: pass=2/2 ... ret=0
gpu_unlock: stage=handoff ret=0
gpu_unlock: unlocked
```

The kernel module was verified within the current initramfs.

## DKMS Integration

DKMS was installed across four observed kernel versions:
- 7.0.0-30-generic-x86_64
- 7.0.0-31-generic-x86_64
- 7.0.0-34-generic-x86_64
- 7.0.0-38-generic-x86_64

Module: `gpu-unlock` version 1.1.0
NVIDIA module: 580.196.07

## Recurring Audit

A recurring RTX 3060 audit timer is enabled to verify unlock activation on each boot.

## Post-Reboot Validation

Non-destructive validation procedure:
1. Check kernel boot log for `gpu_unlock: unlocked` message.
2. Verify module presence in initramfs.
3. Confirm GPU UUID matches expected RTX 3060 identity.
4. Run quick compute sanity test (small CUDA workload).

## Kernel/Driver Update Compatibility

Before kernel or driver updates:
1. Verify DKMS rebuild succeeds for all installed kernels.
2. Confirm `gpu-unlock` module loads without errors.
3. Run post-reboot validation checklist.

## Recovery Procedures

If unlock activation cannot be verified:
1. Check DKMS status: `dkms status gpu-unlock`
2. Rebuild module: `dkms autoinstall`
3. Re-initramfs: `update-initramfs -u -k all`
4. Reboot and verify boot logs.

## Important Caveat

Successful unlock activation is verified. The effective Tensor Core throughput
improvement has not yet been independently quantified with a matched controlled
benchmark. Do not present theoretical speedup as measured result.

## Artifacts

- `/var/lib/dkms/gpu-unlock/`
- `/home/scott/.cache/gpu-unlock/`
- `/home/scott/ai-lab/commissions/rtx3060-unlock-20261026-100601-cHosjf/`
- `/home/scott/ai-lab/results/rtx3060-unlock/`
- `/home/scott/ai-lab/results/rtx3060-unlock-audit/`
- `/home/scott/gpu-unlock-install-20261026-200605.log`
- `/home/scott/Downloads/epyc-rtx3060-unlock-resilience.py`
- `/home/scott/Downloads/enable-rtx3060-gpu-unlock-persistent-v3.py`
- `/home/scott/Downloads/hermes-epyc-rtx3060-unlock.sh`
