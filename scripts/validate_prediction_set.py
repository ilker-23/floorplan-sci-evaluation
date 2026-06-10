#!/usr/bin/env python3
"""Validate prediction JSONL against ground truth and split assignments.

This is the gate before metric computation. It prevents accidental evaluation
on train/validation plans, missing predictions, duplicate plan ids, and room-id
mismatches.
"""
from __future__ import annotations

import argparse
import csv
import json
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
            split_by_plan[row["plan_id"]] = row["split"]
    return split_by_plan


def room_ids(record: dict) -> set[str]:
    return {str(room.get("id")) for room in record.get("rooms", []) if room.get("id") is not None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ground-truth", required=True, type=Path)
    ap.add_argument("--predictions", required=True, type=Path)
    ap.add_argument("--split-assignments", required=True, type=Path)
    ap.add_argument("--split", default="test")
    ap.add_argument("--output-json", type=Path)
    ap.add_argument("--allow-extra-predictions", action="store_true")
    ap.add_argument("--max-errors", type=int, default=50)
    args = ap.parse_args()

    gt = read_jsonl(args.ground_truth)
    pred = read_jsonl(args.predictions)
    split_by_plan = read_split_csv(args.split_assignments)
    expected_ids = {pid for pid, split in split_by_plan.items() if split == args.split}

    errors = []
    gt_ids = set(gt)
    pred_ids = set(pred)
    missing_gt = sorted(expected_ids - gt_ids)
    missing_pred = sorted(expected_ids - pred_ids)
    extra_pred = sorted(pred_ids - expected_ids)
    wrong_split_pred = sorted(pid for pid in pred_ids if split_by_plan.get(pid) not in {args.split, None})

    for pid in missing_gt:
        errors.append({"plan_id": pid, "error": "expected split plan missing from ground truth"})
    for pid in missing_pred:
        errors.append({"plan_id": pid, "error": "expected split plan missing from predictions"})
    if not args.allow_extra_predictions:
        for pid in extra_pred:
            errors.append({"plan_id": pid, "error": "prediction is not part of requested split"})
    for pid in wrong_split_pred:
        errors.append({"plan_id": pid, "error": f"prediction belongs to split {split_by_plan.get(pid)!r}, not {args.split!r}"})

    for pid in sorted(expected_ids & gt_ids & pred_ids):
        gt_rooms = room_ids(gt[pid])
        pred_rooms = room_ids(pred[pid])
        if gt_rooms != pred_rooms:
            errors.append(
                {
                    "plan_id": pid,
                    "error": "room id mismatch",
                    "missing_room_ids": sorted(gt_rooms - pred_rooms),
                    "extra_room_ids": sorted(pred_rooms - gt_rooms),
                }
            )

    summary = {
        "valid": not errors,
        "split": args.split,
        "num_expected": len(expected_ids),
        "num_ground_truth": len(gt),
        "num_predictions": len(pred),
        "num_missing_ground_truth": len(missing_gt),
        "num_missing_predictions": len(missing_pred),
        "num_extra_predictions": len(extra_pred),
        "num_wrong_split_predictions": len(wrong_split_pred),
        "num_errors": len(errors),
        "errors": errors[: args.max_errors],
    }

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
