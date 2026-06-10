#!/usr/bin/env python3
"""Convert Graph2Plan `data_train_converted.pkl` to canonical SCI JSONL.

Observed source structure:
  root keys: data, nameList, trainTF
  data[i] fields: name, boundary, box, order, edge, rBoundary
  box shape:  [num_rooms, 5]
  edge shape: [num_edges, 3]

Default assumptions, matching common Graph2Plan/RPLAN conventions:
  box columns: x1, y1, x2, y2, room_type
  edge columns: room_index_a, room_index_b, relation_type

The converter preserves the numeric room label as `type_id` and maps known ids to
human-readable names where possible. If the label mapping is uncertain, use the
`type_id` values in modelling and update ROOM_TYPE_MAP later.
"""
from __future__ import annotations

import argparse
import json
import pickle
from collections import Counter
from pathlib import Path


ROOM_TYPE_MAP = {
    # Conservative names; keep type_id in every record for traceability.
    0: "LivingRoom",
    1: "MasterRoom",
    2: "Kitchen",
    3: "Bathroom",
    4: "DiningRoom",
    5: "ChildRoom",
    6: "StudyRoom",
    7: "SecondRoom",
    8: "GuestRoom",
    9: "Balcony",
    10: "Storage",
    11: "WC",
    12: "Corridor",
    13: "Other",
}


def scalar(value):
    try:
        return value.item()
    except Exception:
        return value


def to_int(value) -> int:
    return int(scalar(value))


def load_source(path: Path) -> dict:
    with path.open("rb") as f:
        obj = pickle.load(f)
    if not isinstance(obj, dict) or "data" not in obj:
        raise SystemExit("Expected a dict with a 'data' key")
    return obj


def normalize_box(raw, canvas_size: float) -> list[float]:
    vals = [float(v) for v in raw[:4]]
    if canvas_size > 0:
        vals = [v / canvas_size for v in vals]
    x1, y1, x2, y2 = vals
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return [x1, y1, x2, y2]


def edge_index_base(edges, num_rooms: int) -> int:
    if not len(edges):
        return 0
    values = [to_int(v) for row in edges for v in row[:2]]
    if not values:
        return 0
    min_v, max_v = min(values), max(values)
    if min_v >= 1 and max_v <= num_rooms:
        return 1
    return 0


def convert_record(record, index: int, canvas_size: float) -> dict:
    name = str(getattr(record, "name", f"plan_{index:06d}"))
    raw_boxes = getattr(record, "box")
    raw_edges = getattr(record, "edge")
    raw_order = getattr(record, "order", [])
    raw_boundary = getattr(record, "boundary", None)

    rooms = []
    for ridx, row in enumerate(raw_boxes):
        type_id = to_int(row[4]) if len(row) >= 5 else -1
        room = {
            "id": f"r{ridx}",
            "type": ROOM_TYPE_MAP.get(type_id, f"Type{type_id}"),
            "type_id": type_id,
            "box": normalize_box(row, canvas_size),
        }
        try:
            room["order"] = to_int(raw_order[ridx])
        except Exception:
            pass
        rooms.append(room)

    base = edge_index_base(raw_edges, len(rooms))
    edges = []
    edge_relations = []
    for row in raw_edges:
        if len(row) < 2:
            continue
        a = to_int(row[0]) - base
        b = to_int(row[1]) - base
        if a < 0 or b < 0 or a >= len(rooms) or b >= len(rooms) or a == b:
            continue
        edge = tuple(sorted((f"r{a}", f"r{b}")))
        edges.append(edge)
        if len(row) >= 3:
            edge_relations.append({"edge": list(edge), "relation_type": to_int(row[2])})

    unique_edges = sorted(set(edges))
    out = {
        "plan_id": name,
        "family_id": name,
        "source_index": index,
        "source": "graph2plan_data_train_converted",
        "edge_source": "graph2plan_record_edge",
        "rooms": rooms,
        "edges": [list(e) for e in unique_edges],
    }
    if edge_relations:
        out["edge_relations"] = edge_relations
    if raw_boundary is not None:
        out["boundary"] = [[float(v) / canvas_size for v in row] for row in raw_boundary] if canvas_size > 0 else [[float(v) for v in row] for row in raw_boundary]
    return out


def valid_record(record: dict) -> bool:
    if not record["rooms"]:
        return False
    for room in record["rooms"]:
        x1, y1, x2, y2 = room["box"]
        if x2 <= x1 or y2 <= y1:
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--canvas-size", type=float, default=256.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--summary-json", type=Path)
    args = ap.parse_args()

    root = load_source(args.source)
    records = list(root["data"].ravel() if hasattr(root["data"], "ravel") else root["data"])
    if args.limit is not None:
        records = records[: args.limit]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    room_counter = Counter()
    type_counter = Counter()
    edge_counter = Counter()
    with args.output.open("w", encoding="utf-8") as f:
        for idx, rec in enumerate(records):
            converted = convert_record(rec, idx, args.canvas_size)
            if not valid_record(converted):
                skipped += 1
                continue
            f.write(json.dumps(converted, ensure_ascii=False) + "\n")
            written += 1
            room_counter[len(converted["rooms"])] += 1
            edge_counter[len(converted["edges"])] += 1
            for room in converted["rooms"]:
                type_counter[str(room["type_id"])] += 1

    summary = {
        "source": str(args.source),
        "output": str(args.output),
        "canvas_size": args.canvas_size,
        "records_seen": len(records),
        "records_written": written,
        "records_skipped": skipped,
        "room_count_distribution": dict(sorted(room_counter.items())),
        "edge_count_distribution": dict(sorted(edge_counter.items())),
        "room_type_id_distribution": dict(sorted(type_counter.items(), key=lambda kv: int(kv[0]))),
        "edge_source_warning": "Edges are copied from Graph2Plan record.edge; verify whether these are user-program adjacencies or geometry-derived adjacencies before making generation claims.",
    }
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
