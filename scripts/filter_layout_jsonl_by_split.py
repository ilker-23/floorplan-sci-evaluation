#!/usr/bin/env python3
"""Filter canonical layout JSONL records by split assignments.

Use this immediately after `make_splits.py` to create frozen ground-truth files:

  outputs/train_ground_truth.jsonl
  outputs/val_ground_truth.jsonl
  outputs/test_ground_truth.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read_jsonl(path: Path) -> dict[str, dict]:
    records = {}
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            pid = row.get("plan_id")
            if not isinstance(pid, str) or not pid:
                raise SystemExit(f"{path}:{line_no}: missing or invalid plan_id")
            if pid in records:
                raise SystemExit(f"{path}:{line_no}: duplicate plan_id {pid!r}")
            records[pid] = row
    return records


def read_split_csv(path: Path) -> dict[str, str]:
    split_by_plan = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"plan_id", "split"}
        if not required.issubset(reader.fieldnames or []):
            raise SystemExit(f"{path}: required columns {sorted(required)}")
        for row in reader:
            pid = row["plan_id"]
            if pid in split_by_plan:
                raise SystemExit(f"{path}: duplicate plan_id {pid!r}")
            split_by_plan[pid] = row["split"]
    return split_by_plan


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--split-assignments", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--strict", action="store_true", help="Fail if split CSV references missing records")
    args = ap.parse_args()

    records = read_jsonl(args.input)
    split_by_plan = read_split_csv(args.split_assignments)
    rows_by_split: dict[str, list[dict]] = {}
    missing = []
    for pid, split in split_by_plan.items():
        if pid not in records:
            missing.append(pid)
            continue
        rows_by_split.setdefault(split, []).append(records[pid])

    if args.strict and missing:
        raise SystemExit(f"Split file references {len(missing)} missing plan ids; first: {missing[:10]}")

    outputs = {}
    for split, rows in sorted(rows_by_split.items()):
        out_name = f"{args.prefix}{split}_ground_truth.jsonl"
        out_path = args.output_dir / out_name
        write_jsonl(out_path, sorted(rows, key=lambda r: r["plan_id"]))
        outputs[split] = str(out_path)

    counts = Counter(split_by_plan.values())
    summary = {
        "input": str(args.input),
        "split_assignments": str(args.split_assignments),
        "output_dir": str(args.output_dir),
        "counts_in_split_csv": dict(sorted(counts.items())),
        "counts_written": {split: len(rows) for split, rows in sorted(rows_by_split.items())},
        "num_missing_records": len(missing),
        "missing_records": missing[:50],
        "outputs": outputs,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
