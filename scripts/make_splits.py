#!/usr/bin/env python3
"""Create deterministic train/validation/test splits from JSONL metadata.

Input JSONL fields:
  - plan_id: unique plan id
  - family_id: optional grouping key to prevent near-duplicate leakage

Example:
  python3 sci_system/scripts/make_splits.py \
    --input metadata/plans.jsonl \
    --output-dir sci_system/reports/splits \
    --group-key family_id \
    --seed 20260610
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def split_counts(n: int, ratios: dict[str, float]) -> dict[str, int]:
    raw = {name: n * ratio for name, ratio in ratios.items()}
    counts = {name: math.floor(value) for name, value in raw.items()}
    remaining = n - sum(counts.values())
    order = sorted(ratios, key=lambda name: (raw[name] - counts[name], ratios[name]), reverse=True)
    for name in order[:remaining]:
        counts[name] += 1

    positive = [name for name, ratio in ratios.items() if ratio > 0]
    if n >= len(positive):
        for name in positive:
            if counts[name] == 0:
                donor = max((d for d in positive if counts[d] > 1), key=lambda d: counts[d])
                counts[donor] -= 1
                counts[name] += 1
    return counts


def assign_splits(groups: list[str], train: float, val: float, test: float, seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    shuffled = groups[:]
    rng.shuffle(shuffled)
    n = len(shuffled)
    counts = split_counts(n, {"train": train, "val": val, "test": test})
    n_train = counts["train"]
    n_val = counts["val"]
    train_set = set(shuffled[:n_train])
    val_set = set(shuffled[n_train : n_train + n_val])
    split_by_group = {}
    for g in shuffled:
        if g in train_set:
            split_by_group[g] = "train"
        elif g in val_set:
            split_by_group[g] = "val"
        else:
            split_by_group[g] = "test"
    return split_by_group


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--id-key", default="plan_id")
    ap.add_argument("--group-key", default="family_id")
    ap.add_argument("--train-ratio", type=float, default=0.70)
    ap.add_argument("--val-ratio", type=float, default=0.15)
    ap.add_argument("--test-ratio", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=20260610)
    args = ap.parse_args()

    total = args.train_ratio + args.val_ratio + args.test_ratio
    if abs(total - 1.0) > 1e-6:
        raise SystemExit("Split ratios must sum to 1.0")

    rows = read_jsonl(args.input)
    if not rows:
        raise SystemExit("No records found")

    groups_to_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if args.id_key not in row:
            raise SystemExit(f"Missing id key {args.id_key!r} in row: {row}")
        group = str(row.get(args.group_key) or row[args.id_key])
        groups_to_rows[group].append(row)

    split_by_group = assign_splits(
        sorted(groups_to_rows), args.train_ratio, args.val_ratio, args.test_ratio, args.seed
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    split_rows = []
    counts = defaultdict(int)
    for group, group_rows in groups_to_rows.items():
        split = split_by_group[group]
        for row in group_rows:
            split_rows.append(
                {
                    "plan_id": row[args.id_key],
                    "group": group,
                    "split": split,
                }
            )
            counts[split] += 1

    csv_path = args.output_dir / "split_assignments.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["plan_id", "group", "split"])
        writer.writeheader()
        writer.writerows(sorted(split_rows, key=lambda r: str(r["plan_id"])))

    manifest = {
        "input": str(args.input),
        "id_key": args.id_key,
        "group_key": args.group_key,
        "seed": args.seed,
        "ratios": {
            "train": args.train_ratio,
            "val": args.val_ratio,
            "test": args.test_ratio,
        },
        "num_plans": len(rows),
        "num_groups": len(groups_to_rows),
        "counts": dict(sorted(counts.items())),
        "outputs": {"csv": str(csv_path)},
    }
    manifest_path = args.output_dir / "split_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
