#!/usr/bin/env python3
"""
Benchmark reconciler: import raw artifacts into normalized schema, validate schema,
and produce a summary index.

Usage:
    python3 scripts/benchmark-reconcile.py [--dry-run] [--validate-only]

Reads: benchmarks/raw/**/*.{json,csv}
Writes: benchmarks/normalized/*.json, benchmarks/summaries/index.json
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = REPO_ROOT / "benchmarks" / "raw"
NORM_DIR = REPO_ROOT / "benchmarks" / "normalized"
SUMMARY_DIR = REPO_ROOT / "benchmarks" / "summaries"
SCHEMA_PATH = REPO_ROOT / "benchmarks" / "schemas" / "benchmark-schema.json"


def load_schema():
    with open(SCHEMA_PATH, "r") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def categorize_file(path: Path) -> str:
    name = path.name.lower()
    parent = str(path.parent).lower()
    if "rtx3060-unlock-audit" in parent or "audit" in name:
        return "rtx3060-unlock-audit"
    if "rtx3060-unlock" in parent or "unlock" in name:
        return "rtx3060-unlock"
    if "gpu-tuning" in parent:
        return "gpu-tuning"
    if "gpu-optimization" in parent:
        return "gpu-optimization"
    # Check longer phase names first to avoid prefix collisions
    for i in range(11, 0, -1):
        if f"phase{i}" in parent or f"phase-{i}" in parent:
            return f"phase{i}"
    return "unknown"


def import_csv(path: Path, category: str) -> dict:
    """Best-effort import of CSV benchmarks into normalized schema."""
    rows = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return {}

    # Map common column names to schema fields
    first = rows[0]
    result = {
        "id": f"{category}-{path.stem}-{sha256_file(path)[:12]}",
        "timestamp": None,
        "category": category,
        "verification_status": "unverified",
        "confidence": "medium",
        "source_file": str(path),
        "source_sha256": sha256_file(path),
        "row_count": len(rows),
        "columns": list(first.keys()),
        "sample_rows": rows[:5],
    }
    return result


def import_json(path: Path, category: str) -> dict:
    """Best-effort import of JSON benchmarks."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "id": f"{category}-{path.stem}",
            "category": category,
            "verification_status": "failed",
            "confidence": "none",
            "source_file": str(path),
            "error": f"JSON decode error: {e}",
        }

    result = {
        "id": f"{category}-{path.stem}-{sha256_file(path)[:12]}",
        "timestamp": None,
        "category": category,
        "verification_status": "unverified",
        "confidence": "medium",
        "source_file": str(path),
        "source_sha256": sha256_file(path),
        "top_level_keys": list(data.keys()) if isinstance(data, dict) else f"array[{len(data)}]",
        "sample": data if isinstance(data, dict) else data[:3],
    }
    return result


def validate_against_schema(record: dict, schema: dict) -> list:
    """Very light validation: check required fields exist."""
    errors = []
    for field in schema.get("required", []):
        if field not in record:
            errors.append(f"missing required field: {field}")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Benchmark reconciler")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    schema = load_schema()
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    index = {
        "generated_at": None,
        "total_records": 0,
        "categories": {},
        "validation_errors": [],
        "records": [],
    }

    files = sorted(RAW_DIR.rglob("*"))
    for path in files:
        if not path.is_file() or path.suffix.lower() not in (".json", ".csv"):
            continue
        if path.name == "benchmark-schema.json":
            continue

        category = categorize_file(path)
        if path.suffix.lower() == ".csv":
            record = import_csv(path, category)
        else:
            record = import_json(path, category)

        errors = validate_against_schema(record, schema)
        if errors:
            record["validation_errors"] = errors
            index["validation_errors"].extend(errors)

        index["records"].append(record)
        index["total_records"] += 1
        index["categories"][category] = index["categories"].get(category, 0) + 1

        if not args.validate_only:
            out_path = NORM_DIR / f"{category}-{path.stem}.json"
            with open(out_path, "w") as f:
                json.dump(record, f, indent=2, default=str)

    summary_path = SUMMARY_DIR / "index.json"
    index["generated_at"] = __import__("datetime").datetime.now().isoformat()
    with open(summary_path, "w") as f:
        json.dump(index, f, indent=2, default=str)

    print(f"Records processed: {index['total_records']}")
    print(f"Categories: {index['categories']}")
    print(f"Validation errors: {len(index['validation_errors'])}")
    if args.dry_run:
        print("Dry-run: no files written to normalized/")
    else:
        print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
