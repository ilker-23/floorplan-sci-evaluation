#!/usr/bin/env python3
"""Create a train-only program-template layout baseline.

This baseline learns median room boxes from the training split and predicts the
target split from program information only. It is intentionally simple:

1. Prefer an exact ordered room-type signature, e.g. Kitchen,Bathroom,LivingRoom.
2. Fall back to room-count + position + room type.
3. Fall back to room type.
4. Fall back to the global room box median.

The output is a valid prediction JSONL file for the shared evaluator. Do not
report this as a GAN/GNN model result; it is a statistical baseline.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median


Box = tuple[float, float, float, float]


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


def ordered_signature(record: dict) -> tuple[str, ...]:
    return tuple(str(room.get("type", "")) for room in record.get("rooms", []))


def norm_box(box: list[float]) -> Box:
    if len(box) != 4:
        raise ValueError(f"box must have four values: {box}")
    x1, y1, x2, y2 = map(float, box)
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return x1, y1, x2, y2


def median_box(boxes: list[Box]) -> list[float]:
    if not boxes:
        raise ValueError("median_box requires at least one box")
    return [median(values) for values in zip(*boxes)]


def clamp_box(box: list[float]) -> list[float]:
    x1, y1, x2, y2 = box
    x1 = min(1.0, max(0.0, x1))
    y1 = min(1.0, max(0.0, y1))
    x2 = min(1.0, max(0.0, x2))
    y2 = min(1.0, max(0.0, y2))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return [x1, y1, x2, y2]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path, help="Canonical layout JSONL containing all splits")
    ap.add_argument("--split-assignments", required=True, type=Path)
    ap.add_argument("--target-split", default="test")
    ap.add_argument("--source-split", default="train")
    ap.add_argument("--output-jsonl", required=True, type=Path)
    ap.add_argument("--output-summary", type=Path)
    args = ap.parse_args()

    records = read_jsonl(args.input)
    split_by_plan = read_split_csv(args.split_assignments)
    source_records = [
        records[pid]
        for pid, split in split_by_plan.items()
        if split == args.source_split and pid in records
    ]
    target_records = [
        records[pid]
        for pid, split in split_by_plan.items()
        if split == args.target_split and pid in records
    ]
    if not source_records:
        raise SystemExit(f"No source records found for split {args.source_split!r}")
    if not target_records:
        raise SystemExit(f"No target records found for split {args.target_split!r}")

    by_signature_pos: dict[tuple[tuple[str, ...], int], list[Box]] = defaultdict(list)
    by_room_count_type_pos: dict[tuple[int, str, int], list[Box]] = defaultdict(list)
    by_type: dict[str, list[Box]] = defaultdict(list)
    global_boxes: list[Box] = []

    for record in source_records:
        sig = ordered_signature(record)
        rooms = record.get("rooms", [])
        room_count = len(rooms)
        for idx, room in enumerate(rooms):
            rtype = str(room.get("type", ""))
            box = norm_box(room["box"])
            by_signature_pos[(sig, idx)].append(box)
            by_room_count_type_pos[(room_count, rtype, idx)].append(box)
            by_type[rtype].append(box)
            global_boxes.append(box)

    global_template = median_box(global_boxes)
    predictions = []
    fallback_counts = defaultdict(int)
    exact_signature_targets = 0
    exact_position_predictions = 0
    total_rooms = 0

    for target in sorted(target_records, key=lambda r: r["plan_id"]):
        sig = ordered_signature(target)
        rooms = target.get("rooms", [])
        if all((sig, idx) in by_signature_pos for idx in range(len(rooms))):
            exact_signature_targets += 1
        pred_rooms = []
        for idx, room in enumerate(rooms):
            total_rooms += 1
            rtype = str(room.get("type", ""))
            key_exact = (sig, idx)
            key_count_type = (len(rooms), rtype, idx)
            if key_exact in by_signature_pos:
                box = median_box(by_signature_pos[key_exact])
                exact_position_predictions += 1
                source = "exact_ordered_signature_position"
            elif key_count_type in by_room_count_type_pos:
                box = median_box(by_room_count_type_pos[key_count_type])
                source = "room_count_type_position"
            elif rtype in by_type:
                box = median_box(by_type[rtype])
                source = "room_type"
            else:
                box = global_template
                source = "global"
            fallback_counts[source] += 1
            pred_rooms.append(
                {
                    "id": str(room["id"]),
                    "type": room.get("type"),
                    "box": clamp_box(box),
                }
            )
        predictions.append(
            {
                "plan_id": target["plan_id"],
                "family_id": target.get("family_id"),
                "baseline_method": "program_template_train_median",
                "rooms": pred_rooms,
                "edges": target.get("edges", []),
            }
        )

    write_jsonl(args.output_jsonl, predictions)
    summary = {
        "method": "program_template_train_median",
        "input": str(args.input),
        "split_assignments": str(args.split_assignments),
        "source_split": args.source_split,
        "target_split": args.target_split,
        "num_source_records": len(source_records),
        "num_target_records": len(target_records),
        "num_source_ordered_signatures": len({ordered_signature(r) for r in source_records}),
        "output_jsonl": str(args.output_jsonl),
        "exact_signature_target_rate": exact_signature_targets / len(target_records),
        "exact_position_prediction_rate": exact_position_predictions / max(total_rooms, 1),
        "mean_rooms_per_target": mean(len(r.get("rooms", [])) for r in target_records),
        "fallback_room_counts": dict(sorted(fallback_counts.items())),
    }
    if args.output_summary:
        args.output_summary.parent.mkdir(parents=True, exist_ok=True)
        args.output_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
