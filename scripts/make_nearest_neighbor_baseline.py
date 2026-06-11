#!/usr/bin/env python3
"""Create a leakage-free nearest-neighbor layout baseline.

For each target split plan, the script selects one candidate from the training
split using only program-level metadata: room type counts, edge count, and room
count. It then transfers the selected training layout boxes onto the target
room ids by deterministic type/order matching.

This is a retrieval baseline, not a generative model. It is useful because a
new model should beat a simple "reuse a similar training plan" strategy.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean


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


def room_types(record: dict) -> list[str]:
    return [str(room.get("type", "")) for room in record.get("rooms", [])]


def type_counter(record: dict) -> Counter:
    return Counter(room_types(record))


def edge_count(record: dict) -> int:
    return len(record.get("edges", []))


def histogram_l1(a: Counter, b: Counter) -> int:
    keys = set(a) | set(b)
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in keys)


def score_candidate(target: dict, candidate: dict) -> tuple[int, int, int, str]:
    type_mismatch = histogram_l1(type_counter(target), type_counter(candidate))
    room_count_gap = abs(len(target.get("rooms", [])) - len(candidate.get("rooms", [])))
    edge_count_gap = abs(edge_count(target) - edge_count(candidate))
    return (type_mismatch, room_count_gap, edge_count_gap, str(candidate["plan_id"]))


def select_candidate(target: dict, candidates: list[dict]) -> dict:
    if not candidates:
        raise SystemExit("No candidate training records available")
    return min(candidates, key=lambda row: score_candidate(target, row))


def candidate_room_pool(candidate: dict) -> dict[str, list[dict]]:
    pools: dict[str, list[dict]] = {}
    for room in candidate.get("rooms", []):
        pools.setdefault(str(room.get("type", "")), []).append(room)
    return pools


def pop_first_available(pools: dict[str, list[dict]]) -> dict | None:
    for key in sorted(pools):
        if pools[key]:
            return pools[key].pop(0)
    return None


def transfer_boxes(target: dict, candidate: dict) -> tuple[dict, int]:
    pools = candidate_room_pool(candidate)
    fallback_rooms = list(candidate.get("rooms", []))
    if not fallback_rooms:
        raise ValueError(f"Candidate {candidate.get('plan_id')} has no rooms")

    mapped_rooms = []
    fallback_count = 0
    for idx, target_room in enumerate(target.get("rooms", [])):
        rtype = str(target_room.get("type", ""))
        donor = pools.get(rtype, []).pop(0) if pools.get(rtype) else None
        if donor is None:
            donor = pop_first_available(pools) or fallback_rooms[idx % len(fallback_rooms)]
            fallback_count += 1
        mapped_rooms.append(
            {
                "id": str(target_room["id"]),
                "type": target_room.get("type"),
                "box": donor["box"],
            }
        )

    return (
        {
            "plan_id": target["plan_id"],
            "family_id": target.get("family_id"),
            "baseline_source_plan_id": candidate["plan_id"],
            "baseline_method": "nearest_neighbor_train_program_signature",
            "rooms": mapped_rooms,
            "edges": target.get("edges", []),
        },
        fallback_count,
    )


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
    ap.add_argument("--candidate-split", default="train")
    ap.add_argument("--output-jsonl", required=True, type=Path)
    ap.add_argument("--output-summary", type=Path)
    args = ap.parse_args()

    records = read_jsonl(args.input)
    split_by_plan = read_split_csv(args.split_assignments)
    candidates = [
        records[pid]
        for pid, split in split_by_plan.items()
        if split == args.candidate_split and pid in records
    ]
    targets = [
        records[pid]
        for pid, split in split_by_plan.items()
        if split == args.target_split and pid in records
    ]
    if not targets:
        raise SystemExit(f"No target records found for split {args.target_split!r}")
    if not candidates:
        raise SystemExit(f"No candidate records found for split {args.candidate_split!r}")

    predictions = []
    fallback_counts = []
    selected_scores = []
    for target in sorted(targets, key=lambda r: r["plan_id"]):
        candidate = select_candidate(target, candidates)
        prediction, fallback_count = transfer_boxes(target, candidate)
        predictions.append(prediction)
        fallback_counts.append(fallback_count)
        selected_scores.append(score_candidate(target, candidate)[:3])

    write_jsonl(args.output_jsonl, predictions)
    exact_type_matches = sum(1 for score in selected_scores if score[0] == 0)
    summary = {
        "method": "nearest_neighbor_train_program_signature",
        "input": str(args.input),
        "split_assignments": str(args.split_assignments),
        "target_split": args.target_split,
        "candidate_split": args.candidate_split,
        "num_targets": len(targets),
        "num_candidates": len(candidates),
        "output_jsonl": str(args.output_jsonl),
        "exact_type_histogram_match_rate": exact_type_matches / len(targets),
        "mean_room_type_l1": mean(score[0] for score in selected_scores),
        "mean_room_count_gap": mean(score[1] for score in selected_scores),
        "mean_edge_count_gap": mean(score[2] for score in selected_scores),
        "mean_fallback_room_mappings": mean(fallback_counts),
        "plans_with_fallback_room_mapping_rate": sum(v > 0 for v in fallback_counts) / len(fallback_counts),
    }
    if args.output_summary:
        args.output_summary.parent.mkdir(parents=True, exist_ok=True)
        args.output_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
