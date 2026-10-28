#!/usr/bin/env python3
"""
Tests for EPYC infrastructure knowledge repo.
Run: python3 tests/test_benchmark_schema.py
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "benchmarks" / "schemas" / "benchmark-schema.json"
NORM_DIR = REPO_ROOT / "benchmarks" / "normalized"
SUMMARY_PATH = REPO_ROOT / "benchmarks" / "summaries" / "index.json"


def test_schema_loads():
    with open(SCHEMA_PATH, "r") as f:
        schema = json.load(f)
    assert "title" in schema
    assert schema["title"] == "BenchmarkRecord"
    print("PASS: schema loads")


def test_normalized_records_exist():
    files = list(NORM_DIR.glob("*.json"))
    assert len(files) >= 10, f"Expected >=10 normalized records, got {len(files)}"
    print(f"PASS: {len(files)} normalized records exist")


def test_summary_index():
    with open(SUMMARY_PATH, "r") as f:
        index = json.load(f)
    assert "total_records" in index
    assert index["total_records"] >= 10
    assert "categories" in index
    print(f"PASS: summary index has {index['total_records']} records")


def test_gpu_identity_schema():
    with open(REPO_ROOT / "configs" / "hardware" / "gpu-identity.json", "r") as f:
        data = json.load(f)
    assert "gpus" in data
    assert len(data["gpus"]) == 3
    gpu_names = [g["name"] for g in data["gpus"]]
    assert any("V100" in n for n in gpu_names)
    assert any("P40" in n for n in gpu_names)
    assert any("3060" in n for n in gpu_names)
    print("PASS: gpu-identity.json has 3 GPUs with expected names")


def test_readme_exists():
    readme = REPO_ROOT / "README.md"
    assert readme.exists()
    content = readme.read_text()
    assert "EPYC" in content
    assert "V100" in content
    assert "P40" in content
    assert "RTX 3060" in content
    print("PASS: README.md contains key hardware names")


def test_skill_file_exists():
    skill = REPO_ROOT / "skills" / "hermes" / "epyc-compute-intelligence.md"
    assert skill.exists()
    content = skill.read_text()
    assert "VRAM" in content
    assert "V100" in content
    assert "P40" in content
    print("PASS: Hermes skill file exists and references GPUs")


def main():
    tests = [
        test_schema_loads,
        test_normalized_records_exist,
        test_summary_index,
        test_gpu_identity_schema,
        test_readme_exists,
        test_skill_file_exists,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
