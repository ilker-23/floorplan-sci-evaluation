#!/usr/bin/env python3
"""Validate the canonical SCI layout JSONL schema.

This script is the first gate after converting RPLAN/Graph2Plan data. It checks
record structure, room ids, boxes, edge references, and optional normalized-box
constraints. It does not evaluate model quality.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_jsonl(path: Path) -> list[tuple[int, dict]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            rows.append((line_no, value))
    return rows


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_box(box, normalized: bool) -> list[str]:
    errors = []
    if not isinstance(box, list) or len(box) != 4:
        return ["box must be a list of four numeric values"]
    if not all(is_number(v) for v in box):
        return ["box values must be numeric"]
    x1, y1, x2, y2 = [float(v) for v in box]
    if x2 <= x1 or y2 <= y1:
        errors.append("box must satisfy x2 > x1 and y2 > y1")
    if normalized and any(v < 0.0 or v > 1.0 for v in [x1, y1, x2, y2]):
        errors.append("normalized box values must be within [0, 1]")
    return errors


def validate_record(record: dict, line_no: int, normalized: bool) -> list[dict]:
    errors = []
    if not isinstance(record, dict):
        return [{"line": line_no, "field": "<record>", "error": "record must be an object"}]

    plan_id = record.get("plan_id")
    if not isinstance(plan_id, str) or not plan_id:
        errors.append({"line": line_no, "field": "plan_id", "error": "plan_id must be a non-empty string"})

    rooms = record.get("rooms")
    if not isinstance(rooms, list) or not rooms:
        errors.append({"line": line_no, "field": "rooms", "error": "rooms must be a non-empty list"})
        rooms = []

    room_ids = []
    for idx, room in enumerate(rooms):
        field = f"rooms[{idx}]"
        if not isinstance(room, dict):
            errors.append({"line": line_no, "field": field, "error": "room must be an object"})
            continue
        rid = room.get("id")
        if not isinstance(rid, str) or not rid:
            errors.append({"line": line_no, "field": field + ".id", "error": "room id must be a non-empty string"})
        else:
            room_ids.append(rid)
        rtype = room.get("type")
        if not isinstance(rtype, str) or not rtype:
            errors.append({"line": line_no, "field": field + ".type", "error": "room type must be a non-empty string"})
        if "box" not in room:
            errors.append({"line": line_no, "field": field + ".box", "error": "missing box"})
        else:
            for err in validate_box(room["box"], normalized):
                errors.append({"line": line_no, "field": field + ".box", "error": err})

    duplicate_rooms = [rid for rid, count in Counter(room_ids).items() if count > 1]
    for rid in duplicate_rooms:
        errors.append({"line": line_no, "field": "rooms", "error": f"duplicate room id {rid!r}"})

    valid_room_ids = set(room_ids)
    edges = record.get("edges", [])
    if not isinstance(edges, list):
        errors.append({"line": line_no, "field": "edges", "error": "edges must be a list"})
        edges = []
    seen_edges = set()
    for idx, edge in enumerate(edges):
        field = f"edges[{idx}]"
        if not isinstance(edge, list) or len(edge) != 2:
            errors.append({"line": line_no, "field": field, "error": "edge must be a two-item list"})
            continue
        a, b = edge
        if not isinstance(a, str) or not isinstance(b, str):
            errors.append({"line": line_no, "field": field, "error": "edge endpoints must be room id strings"})
            continue
        if a == b:
            errors.append({"line": line_no, "field": field, "error": "self-edge is not allowed"})
        if a not in valid_room_ids:
            errors.append({"line": line_no, "field": field, "error": f"unknown room id {a!r}"})
        if b not in valid_room_ids:
            errors.append({"line": line_no, "field": field, "error": f"unknown room id {b!r}"})
        key = tuple(sorted((a, b)))
        if key in seen_edges:
            errors.append({"line": line_no, "field": field, "error": f"duplicate edge {list(key)!r}"})
        seen_edges.add(key)

    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output-json", type=Path)
    ap.add_argument("--allow-unnormalized-boxes", action="store_true")
    ap.add_argument("--max-errors", type=int, default=50)
    args = ap.parse_args()

    rows = load_jsonl(args.input)
    errors = []
    plan_ids = []
    room_counts = []
    edge_counts = []
    for line_no, record in rows:
        if isinstance(record, dict) and isinstance(record.get("plan_id"), str):
            plan_ids.append(record["plan_id"])
        if isinstance(record, dict) and isinstance(record.get("rooms"), list):
            room_counts.append(len(record["rooms"]))
        if isinstance(record, dict) and isinstance(record.get("edges", []), list):
            edge_counts.append(len(record.get("edges", [])))
        errors.extend(validate_record(record, line_no, not args.allow_unnormalized_boxes))

    duplicate_plan_ids = [pid for pid, count in Counter(plan_ids).items() if count > 1]
    for pid in duplicate_plan_ids:
        errors.append({"line": None, "field": "plan_id", "error": f"duplicate plan_id {pid!r}"})

    summary = {
        "input": str(args.input),
        "valid": not errors,
        "num_records": len(rows),
        "num_errors": len(errors),
        "duplicate_plan_ids": duplicate_plan_ids[: args.max_errors],
        "min_rooms": min(room_counts) if room_counts else None,
        "max_rooms": max(room_counts) if room_counts else None,
        "mean_rooms": sum(room_counts) / len(room_counts) if room_counts else None,
        "min_edges": min(edge_counts) if edge_counts else None,
        "max_edges": max(edge_counts) if edge_counts else None,
        "mean_edges": sum(edge_counts) / len(edge_counts) if edge_counts else None,
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
