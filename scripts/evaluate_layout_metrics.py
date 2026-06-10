#!/usr/bin/env python3
"""Evaluate room-box floor-plan predictions from JSONL files.

Expected JSONL format for ground truth and predictions:
  {
    "plan_id": "plan_001",
    "rooms": [{"id": "r1", "type": "Kitchen", "box": [x1,y1,x2,y2]}, ...],
    "edges": [["r1","r2"], ...]
  }

The evaluator matches rooms by id. Boxes are expected in normalized coordinates.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev


EPS = 1e-9


def read_jsonl(path: Path) -> dict[str, dict]:
    records = {}
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            pid = row.get("plan_id")
            if pid is None:
                raise SystemExit(f"{path}:{line_no}: missing plan_id")
            if pid in records:
                raise SystemExit(f"{path}:{line_no}: duplicate plan_id {pid}")
            records[str(pid)] = row
    return records


def norm_box(box: list[float]) -> tuple[float, float, float, float]:
    if len(box) != 4:
        raise ValueError(f"box must have four values: {box}")
    x1, y1, x2, y2 = map(float, box)
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return x1, y1, x2, y2


def area(b: tuple[float, float, float, float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection(a, b) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def iou(a, b) -> float:
    inter = intersection(a, b)
    union = area(a) + area(b) - inter
    return inter / union if union > EPS else 0.0


def out_of_bounds_area(b) -> float:
    inside = (
        max(0.0, min(1.0, b[2]) - max(0.0, b[0]))
        * max(0.0, min(1.0, b[3]) - max(0.0, b[1]))
    )
    return max(0.0, area(b) - inside)


def contact(a, b, tol: float) -> bool:
    x_overlap = min(a[2], b[2]) - max(a[0], b[0])
    y_overlap = min(a[3], b[3]) - max(a[1], b[1])
    horizontal_touch = abs(a[2] - b[0]) <= tol or abs(b[2] - a[0]) <= tol
    vertical_touch = abs(a[3] - b[1]) <= tol or abs(b[3] - a[1]) <= tol
    return (horizontal_touch and y_overlap > tol) or (vertical_touch and x_overlap > tol)


def edge_key(edge) -> tuple[str, str]:
    a, b = map(str, edge)
    return tuple(sorted((a, b)))


def recovered_edges(room_boxes: dict[str, tuple], tol: float) -> set[tuple[str, str]]:
    ids = sorted(room_boxes)
    edges = set()
    for idx, a_id in enumerate(ids):
        for b_id in ids[idx + 1 :]:
            if contact(room_boxes[a_id], room_boxes[b_id], tol):
                edges.add((a_id, b_id))
    return edges


def overlap_ratio(room_boxes: dict[str, tuple]) -> tuple[float, bool]:
    total_area = sum(area(b) for b in room_boxes.values())
    overlap = 0.0
    ids = sorted(room_boxes)
    for idx, a_id in enumerate(ids):
        for b_id in ids[idx + 1 :]:
            overlap += intersection(room_boxes[a_id], room_boxes[b_id])
    return overlap / max(total_area, EPS), overlap > EPS


def graph_connected(nodes: set[str], edges: set[tuple[str, str]]) -> bool:
    if not nodes:
        return False
    adj = {n: set() for n in nodes}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    seen = set()
    stack = [next(iter(nodes))]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(adj[n] - seen)
    return seen == nodes


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    vals = sorted(values)
    pos = (len(vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def summarize(values: list[float]) -> dict:
    if not values:
        return {"mean": None, "std": None, "median": None, "q25": None, "q75": None}
    return {
        "mean": mean(values),
        "std": pstdev(values),
        "median": median(values),
        "q25": percentile(values, 0.25),
        "q75": percentile(values, 0.75),
    }


def evaluate_plan(gt: dict, pred: dict, contact_tol: float) -> dict:
    gt_rooms = {str(r["id"]): r for r in gt.get("rooms", [])}
    pred_rooms = {str(r["id"]): r for r in pred.get("rooms", [])}
    common = sorted(set(gt_rooms) & set(pred_rooms))
    if not common:
        raise ValueError(f"No common room ids for plan {gt.get('plan_id')}")

    gt_boxes = {rid: norm_box(gt_rooms[rid]["box"]) for rid in common}
    pred_boxes = {rid: norm_box(pred_rooms[rid]["box"]) for rid in common}

    ious = [iou(pred_boxes[rid], gt_boxes[rid]) for rid in common]
    pred_overlap_ratio, pred_has_overlap = overlap_ratio(pred_boxes)
    gt_overlap_ratio, gt_has_overlap = overlap_ratio(gt_boxes)
    oob = sum(out_of_bounds_area(b) for b in pred_boxes.values())
    pred_total_area = sum(area(b) for b in pred_boxes.values())

    area_errors = []
    aspect_errors = []
    for rid in common:
        ga = area(gt_boxes[rid])
        pa = area(pred_boxes[rid])
        area_errors.append(abs(pa - ga) / max(ga, EPS))
        gw = max(gt_boxes[rid][2] - gt_boxes[rid][0], EPS)
        gh = max(gt_boxes[rid][3] - gt_boxes[rid][1], EPS)
        pw = max(pred_boxes[rid][2] - pred_boxes[rid][0], EPS)
        ph = max(pred_boxes[rid][3] - pred_boxes[rid][1], EPS)
        aspect_errors.append(abs((pw / ph) - (gw / gh)))

    target_edges = {edge_key(e) for e in gt.get("edges", [])}
    pred_edges = recovered_edges(pred_boxes, contact_tol)
    tp = len(target_edges & pred_edges)
    precision = tp / len(pred_edges) if pred_edges else (1.0 if not target_edges else 0.0)
    recall = tp / len(target_edges) if target_edges else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > EPS else 0.0
    ged_simple = (len(target_edges - pred_edges) + len(pred_edges - target_edges)) / max(
        len(common) + len(target_edges), 1
    )

    return {
        "plan_id": gt["plan_id"],
        "room_count": len(common),
        "miou": mean(ious),
        "min_iou": min(ious),
        "overlap_ratio": pred_overlap_ratio,
        "gt_overlap_ratio": gt_overlap_ratio,
        "overlap_excess_ratio": max(0.0, pred_overlap_ratio - gt_overlap_ratio),
        "overlap_delta_abs": abs(pred_overlap_ratio - gt_overlap_ratio),
        "has_overlap": pred_has_overlap,
        "gt_has_overlap": gt_has_overlap,
        "boundary_violation_ratio": oob / max(pred_total_area, EPS),
        "has_boundary_violation": oob > EPS,
        "area_mape": mean(area_errors),
        "aspect_error": mean(aspect_errors),
        "adj_precision": precision,
        "adj_recall": recall,
        "adj_f1": f1,
        "ged_simple": ged_simple,
        "connectivity_valid": graph_connected(set(common), pred_edges),
    }


def bucket(room_count: int) -> str:
    if room_count <= 5:
        return "4-5"
    if room_count <= 7:
        return "6-7"
    return "8+"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ground-truth", required=True, type=Path)
    ap.add_argument("--predictions", required=True, type=Path)
    ap.add_argument("--output-json", required=True, type=Path)
    ap.add_argument("--by-room-count-csv", type=Path)
    ap.add_argument("--contact-tol", type=float, default=1e-3)
    args = ap.parse_args()

    gt = read_jsonl(args.ground_truth)
    pred = read_jsonl(args.predictions)
    common_ids = sorted(set(gt) & set(pred))
    if not common_ids:
        raise SystemExit("No matching plan_id values between ground truth and predictions")

    per_plan = []
    missing_pred = sorted(set(gt) - set(pred))
    for pid in common_ids:
        per_plan.append(evaluate_plan(gt[pid], pred[pid], args.contact_tol))

    metric_keys = [
        "miou",
        "min_iou",
        "overlap_ratio",
        "gt_overlap_ratio",
        "overlap_excess_ratio",
        "overlap_delta_abs",
        "boundary_violation_ratio",
        "area_mape",
        "aspect_error",
        "adj_precision",
        "adj_recall",
        "adj_f1",
        "ged_simple",
    ]
    summary = {k: summarize([float(r[k]) for r in per_plan]) for k in metric_keys}
    summary.update(
        {
            "num_ground_truth": len(gt),
            "num_predictions": len(pred),
            "num_evaluated": len(per_plan),
            "num_missing_predictions": len(missing_pred),
            "miou_above_0_50": sum(r["miou"] >= 0.50 for r in per_plan) / len(per_plan),
            "miou_above_0_70": sum(r["miou"] >= 0.70 for r in per_plan) / len(per_plan),
            "plans_with_overlap": sum(r["has_overlap"] for r in per_plan) / len(per_plan),
            "gt_plans_with_overlap": sum(r["gt_has_overlap"] for r in per_plan) / len(per_plan),
            "oracle_like_warning": {
                "meaning": "If predictions are an exact GT copy, mIoU should be 1.0. Nonzero GT overlap or low adjacency recall indicates dataset/edge representation effects, not model errors.",
                "gt_overlap_mean": summarize([float(r["gt_overlap_ratio"]) for r in per_plan])["mean"],
                "adjacency_is_geometry_recovered": False,
            },
            "plans_with_boundary_violation": sum(r["has_boundary_violation"] for r in per_plan)
            / len(per_plan),
            "connectivity_valid_rate": sum(r["connectivity_valid"] for r in per_plan)
            / len(per_plan),
        }
    )
    output = {"summary": summary, "per_plan": per_plan}
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2), encoding="utf-8")

    if args.by_room_count_csv:
        args.by_room_count_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for group in ["4-5", "6-7", "8+"]:
            group_rows = [r for r in per_plan if bucket(r["room_count"]) == group]
            if not group_rows:
                continue
            row = {"room_count": group, "n": len(group_rows)}
            for key in [
                "miou",
                "adj_f1",
                "overlap_ratio",
                "gt_overlap_ratio",
                "overlap_excess_ratio",
                "boundary_violation_ratio",
            ]:
                row[f"{key}_mean"] = mean(float(r[key]) for r in group_rows)
                row[f"{key}_std"] = pstdev(float(r[key]) for r in group_rows)
            rows.append(row)
        with args.by_room_count_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["room_count"])
            writer.writeheader()
            writer.writerows(rows)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
