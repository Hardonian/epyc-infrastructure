#!/usr/bin/env bash
# EPYC Infrastructure Drift Inspector
# Runs drift-inspector against EPYC infrastructure configs and reports diffs.
set -Eeuo pipefail

DRIFT_INSPECTOR="/home/scott/ai-workspace/repos/ops-tools/drift-inspector"
EPYC_REPO="/home/scott/ai-workspace/repos/epyc-infrastructure-knowledge"
REPORT_DIR="${EPYC_REPO}/benchmarks/drift-reports"

mkdir -p "${REPORT_DIR}"

if [ ! -d "${DRIFT_INSPECTOR}" ]; then
  echo "FATAL: drift-inspector not found at ${DRIFT_INSPECTOR}" >&2
  exit 1
fi

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
REPORT_FILE="${REPORT_DIR}/drift-${TIMESTAMP}.json"

echo "[INFO] Running drift inspection against EPYC configs..."
cd "${DRIFT_INSPECTOR}" && python -m drift_inspector.cli \
  --config "${EPYC_REPO}/configs" \
  --output "${REPORT_FILE}" 2>&1 || true

if [ -f "${REPORT_FILE}" ]; then
  echo "[INFO] Drift report written to ${REPORT_FILE}"
  python3 -m json.tool "${REPORT_FILE}" | tail -20
else
  echo "[WARN] No drift report generated"
fi
