#!/usr/bin/env python3
"""Template converter from an RPLAN/Graph2Plan-like source to SCI JSONL.

RPLAN copies differ. Do not blindly trust this file. First run:

  python sci_system/colab/inspect_drive_dataset.py --root YOUR_RPLAN_DIR ...

Then edit `convert_record()` below to match your actual data structure.
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path


ROOM_TYPE_MAP = {
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
}


def load_source(path: Path):
    suffix = path.suffix.lower()
    if suffix in {".pkl", ".pickle"}:
        with path.open("rb") as f:
            return pickle.load(f)
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    raise SystemExit(f"Unsupported source type: {path}")


def as_box_xyxy(raw_box):
    """Convert common box formats to normalized [x1,y1,x2,y2].

    Edit if your data uses pixels or [cx,cy,w,h].
    """
    vals = [float(v) for v in raw_box]
    if len(vals) != 4:
        raise ValueError(f"Bad box: {raw_box}")
    x1, y1, x2, y2 = vals
    if max(vals) > 1.5:
        # Common RPLAN raster size is 256; adjust if your data differs.
        x1, y1, x2, y2 = [v / 256.0 for v in vals]
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return [x1, y1, x2, y2]


def convert_record(raw, index: int) -> dict:
    """Convert one raw record.

    You almost certainly need to edit this function after inspecting your data.

    Accepted example input shapes:
      {"id": "...", "rooms": [{"id":..., "type":..., "box":...}], "edges": [[...]]}
      {"boxes": [...], "room_types": [...], "edges": [[0,1], ...]}
    """
    if not isinstance(raw, dict):
        raise ValueError(f"Expected dict record, got {type(raw).__name__}")

    plan_id = str(raw.get("plan_id") or raw.get("id") or raw.get("name") or f"plan_{index:06d}")
    family_id = str(raw.get("family_id") or raw.get("source_id") or plan_id)

    rooms = []
    if "rooms" in raw:
        for ridx, room in enumerate(raw["rooms"]):
            room_id = str(room.get("id", f"r{ridx}"))
            rtype = room.get("type", room.get("label", room.get("category", "Unknown")))
            if isinstance(rtype, int):
                rtype = ROOM_TYPE_MAP.get(rtype, f"Type{rtype}")
            box = room.get("box") or room.get("bbox") or room.get("bounds")
            if box is None:
                raise ValueError(f"Missing box in room {room}")
            rooms.append({"id": room_id, "type": str(rtype), "box": as_box_xyxy(box)})
    elif "boxes" in raw:
        labels = raw.get("room_types") or raw.get("labels") or ["Unknown"] * len(raw["boxes"])
        for ridx, box in enumerate(raw["boxes"]):
            rtype = labels[ridx] if ridx < len(labels) else "Unknown"
            if isinstance(rtype, int):
                rtype = ROOM_TYPE_MAP.get(rtype, f"Type{rtype}")
            rooms.append({"id": f"r{ridx}", "type": str(rtype), "box": as_box_xyxy(box)})
    else:
        raise ValueError(f"Cannot find rooms/boxes keys. Available keys: {list(raw.keys())}")

    id_by_index = {idx: room["id"] for idx, room in enumerate(rooms)}
    edges = []
    for edge in raw.get("edges", raw.get("graph", raw.get("adjacency", []))):
        if len(edge) < 2:
            continue
        a, b = edge[0], edge[1]
        a = id_by_index.get(a, str(a)) if isinstance(a, int) else str(a)
        b = id_by_index.get(b, str(b)) if isinstance(b, int) else str(b)
        if a != b:
            edges.append(sorted([a, b]))

    edges = sorted({tuple(e) for e in edges})
    return {"plan_id": plan_id, "family_id": family_id, "rooms": rooms, "edges": [list(e) for e in edges]}


def iter_records(obj):
    if isinstance(obj, list):
        yield from obj
    elif isinstance(obj, dict):
        for key in ["records", "data", "plans", "samples"]:
            if key in obj and isinstance(obj[key], list):
                yield from obj[key]
                return
        # If dict maps id -> record
        if all(isinstance(v, dict) for v in obj.values()):
            for key, value in obj.items():
                value = dict(value)
                value.setdefault("plan_id", key)
                yield value
            return
        raise SystemExit(f"Cannot find record list in dict keys: {list(obj.keys())[:30]}")
    else:
        raise SystemExit(f"Unsupported root object type: {type(obj).__name__}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    source = load_source(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    errors = []
    with args.output.open("w", encoding="utf-8") as f:
        for idx, raw in enumerate(iter_records(source)):
            if args.limit is not None and count >= args.limit:
                break
            try:
                converted = convert_record(raw, idx)
            except Exception as exc:
                errors.append({"index": idx, "error": type(exc).__name__ + ": " + str(exc)[:300]})
                continue
            f.write(json.dumps(converted, ensure_ascii=False) + "\n")
            count += 1
    report = {"source": str(args.source), "output": str(args.output), "converted": count, "errors": errors[:20], "num_errors": len(errors)}
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
