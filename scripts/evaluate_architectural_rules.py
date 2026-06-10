#!/usr/bin/env python3
"""Evaluate architectural screening rules for layout JSONL records.

This script is deliberately conservative. It does not certify constructability.
It only reports geometric and preliminary architectural plausibility warnings.

Input JSONL format:
  {
    "plan_id": "...",
    "scale_m2_per_unit_area": 80.0,       # optional for normalized boxes
    "rooms": [
      {"id":"r1","type":"LivingRoom","box":[x1,y1,x2,y2]},
      {"id":"r2","type":"Kitchen","box_m":[0,0,3,3]}
    ],
    "edges": [["r1","r2"]]
  }
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


EPS = 1e-9


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


def norm_box(values) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = map(float, values)
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return x1, y1, x2, y2


def area(box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def intersection(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0.0, min(a[3], b[3]) - max(a[1], b[1])
    )


def aspect_ratio(box) -> float:
    w = max(box[2] - box[0], EPS)
    h = max(box[3] - box[1], EPS)
    return max(w / h, h / w)


def edge_key(edge) -> tuple[str, str]:
    a, b = map(str, edge)
    return tuple(sorted((a, b)))


def connected(nodes: set[str], edges: set[tuple[str, str]]) -> bool:
    if not nodes:
        return False
    graph = {n: set() for n in nodes}
    for a, b in edges:
        if a in graph and b in graph:
            graph[a].add(b)
            graph[b].add(a)
    seen = set()
    stack = [next(iter(nodes))]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph[node] - seen)
    return seen == nodes


def room_area_m2(record: dict, room: dict, box) -> float | None:
    if "area_m2" in room:
        return float(room["area_m2"])
    if "box_m" in room:
        return area(norm_box(room["box_m"]))
    scale = record.get("scale_m2_per_unit_area")
    if scale is not None:
        return area(box) * float(scale)
    return None


def evaluate_record(record: dict, rules: dict) -> dict:
    plan_id = str(record.get("plan_id", "UNKNOWN"))
    rooms = {str(room["id"]): room for room in record.get("rooms", [])}
    boxes = {rid: norm_box(room.get("box_m") or room["box"]) for rid, room in rooms.items()}
    room_types = {rid: str(room.get("type", "Unknown")) for rid, room in rooms.items()}
    edges = {edge_key(edge) for edge in record.get("edges", [])}
    nodes = set(rooms)
    warnings = []

    total_area = sum(area(box) for box in boxes.values())
    overlap_area = 0.0
    ids = sorted(boxes)
    for idx, a_id in enumerate(ids):
        for b_id in ids[idx + 1 :]:
            overlap_area += intersection(boxes[a_id], boxes[b_id])
    overlap_ratio = overlap_area / max(total_area, EPS)
    if overlap_ratio > float(rules.get("overlap_tolerance_ratio", 0.001)):
        warnings.append({"rule": "room_overlap", "value": overlap_ratio})

    oob_area = 0.0
    for rid, box in boxes.items():
        inside = max(0.0, min(1.0, box[2]) - max(0.0, box[0])) * max(
            0.0, min(1.0, box[3]) - max(0.0, box[1])
        )
        oob_area += max(0.0, area(box) - inside)
    boundary_ratio = oob_area / max(total_area, EPS)
    if boundary_ratio > float(rules.get("boundary_tolerance_ratio", 0.000001)):
        warnings.append({"rule": "boundary_violation", "value": boundary_ratio})

    max_aspect = rules.get("max_aspect_ratio", {})
    default_max_aspect = float(max_aspect.get("default", 4.0))
    for rid, box in boxes.items():
        rtype = room_types[rid]
        limit = float(max_aspect.get(rtype, default_max_aspect))
        ar = aspect_ratio(box)
        if ar > limit:
            warnings.append({"rule": "aspect_ratio", "room_id": rid, "room_type": rtype, "value": ar, "limit": limit})

    min_area = rules.get("min_area_m2", {})
    area_checks_available = 0
    for rid, room in rooms.items():
        rtype = room_types[rid]
        if rtype not in min_area:
            continue
        measured = room_area_m2(record, room, boxes[rid])
        if measured is None:
            continue
        area_checks_available += 1
        limit = float(min_area[rtype])
        if measured < limit:
            warnings.append({"rule": "min_area_m2", "room_id": rid, "room_type": rtype, "value": measured, "limit": limit})

    if rules.get("rules", {}).get("require_connected_graph", True) and not connected(nodes, edges):
        warnings.append({"rule": "disconnected_adjacency_graph"})

    service_types = set(rules.get("service_room_types", []))
    private_types = set(rules.get("private_room_types", []))
    if rules.get("rules", {}).get("flag_isolated_service_rooms", True):
        degree = Counter()
        for a, b in edges:
            degree[a] += 1
            degree[b] += 1
        for rid, rtype in room_types.items():
            if rtype in service_types and degree[rid] == 0:
                warnings.append({"rule": "isolated_service_room", "room_id": rid, "room_type": rtype})

    if rules.get("rules", {}).get("flag_private_room_as_only_access_to_service", True):
        adj = defaultdict(set)
        for a, b in edges:
            adj[a].add(b)
            adj[b].add(a)
        for rid, rtype in room_types.items():
            if rtype not in service_types:
                continue
            neighbours = adj[rid]
            if neighbours and all(room_types.get(n) in private_types for n in neighbours):
                warnings.append({"rule": "service_only_accessed_from_private_room", "room_id": rid, "room_type": rtype})

    return {
        "plan_id": plan_id,
        "room_count": len(rooms),
        "overlap_ratio": overlap_ratio,
        "boundary_violation_ratio": boundary_ratio,
        "area_checks_available": area_checks_available,
        "warning_count": len(warnings),
        "valid_level_1_screen": len(warnings) == 0,
        "warnings": warnings,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layouts", required=True, type=Path)
    ap.add_argument("--rules", required=True, type=Path)
    ap.add_argument("--output-json", required=True, type=Path)
    args = ap.parse_args()

    records = read_jsonl(args.layouts)
    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    per_plan = [evaluate_record(record, rules) for record in records]
    warning_counter = Counter()
    for row in per_plan:
        for warning in row["warnings"]:
            warning_counter[warning["rule"]] += 1

    summary = {
        "num_plans": len(per_plan),
        "level_1_screen_pass_rate": sum(r["valid_level_1_screen"] for r in per_plan) / max(len(per_plan), 1),
        "mean_warning_count": mean(r["warning_count"] for r in per_plan) if per_plan else 0.0,
        "mean_overlap_ratio": mean(r["overlap_ratio"] for r in per_plan) if per_plan else 0.0,
        "mean_boundary_violation_ratio": mean(r["boundary_violation_ratio"] for r in per_plan) if per_plan else 0.0,
        "warning_counts": dict(sorted(warning_counter.items())),
        "area_checks_available_rate": sum(r["area_checks_available"] > 0 for r in per_plan) / max(len(per_plan), 1),
    }

    output = {"summary": summary, "per_plan": per_plan}
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
