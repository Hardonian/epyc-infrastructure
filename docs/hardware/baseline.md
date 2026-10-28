# Hardware Baseline

## Verified Configuration (2026-10-27)

### CPU
- Model: AMD EPYC 7452 32-Core Processor
- Sockets: 1
- Cores per socket: 32
- Threads per core: 2
- Total logical CPUs: 64
- Max frequency: 3364 MHz
- Min frequency: 1500 MHz

### Memory
- Total RAM: 168 GiB ECC
- NUMA nodes: 1 (node 0: CPUs 0-63)
- Firmware memory speed: not available via dmidecode (sudo required)
- Swap: 32 GiB + 32 GiB zram

### Storage
| Device | Size | Type | Mount |
|---|---|---|---|
| nvme0n1 (Micron 2300) | 512 GB | NVMe | /boot + LVM root |
| nvme1n1 (KINGSTON OM3PGP4) | 1 TB | NVMe | /mnt/ai-storage |
| sda (USB HDD) | 931 GB | USB HDD | /mnt/ai-storage/hdd1 |
| sdb (USB HDD) | 466 GB | USB HDD | /mnt/ai-storage/hdd2 + scratch |
| zram0 | 32 GB | compressed swap | swap |

### Motherboard / BIOS
- Board vendor: AMD Corporation
- Board name: Ethanol-X
- BIOS vendor: American Megatrends Inc.
- BIOS version: 0.3
- BIOS date: 2025-05-15

## Differences from Historical Baseline

The commission baseline listed ~168 GiB usable ECC RAM at 2133 MT/s. Current live
state confirms 168 GiB total but firmware speed is not readable without sudo. Treat
2133 MT/s as a lower-bound historical observation, not a guaranteed current speed.

## NUMA Topology

Single NUMA node. All GPUs and memory are on node 0. No cross-node traffic.

## Power and Thermal Limits

| GPU | Stock Power Cap | Idle Watchdog Target | Thermal Warn | Thermal Throttle |
|---|---|---|---|---|
| V100 | 300W | 200W | 78°C | 84°C |
| P40 | 175W | 175W | 90°C | 96°C |
| RTX 3060 | 170W | 170W | 78°C | 83°C |

P40 tuning is reapplied at boot via `gpu-tuning-apply.service` (root, oneshot).
