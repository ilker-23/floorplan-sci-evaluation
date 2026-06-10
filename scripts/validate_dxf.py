#!/usr/bin/env python3
"""Dependency-free DXF structural validator.

This is intentionally conservative. It checks whether DXF files contain usable
room-layer geometry, not whether they are complete architectural drawings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median


ENTITY_TYPES = {"LINE", "POLYLINE", "LWPOLYLINE", "TEXT", "MTEXT", "CIRCLE", "INSERT", "HATCH"}


def parse_pairs(text: str) -> list[tuple[str, str]]:
    lines = [line.rstrip("\r\n") for line in text.splitlines()]
    pairs = []
    for i in range(0, len(lines) - 1, 2):
        pairs.append((lines[i].strip(), lines[i + 1].strip()))
    return pairs


def validate_file(path: Path) -> dict:
    text = path.read_text(errors="ignore")
    pairs = parse_pairs(text)
    entity_counts = {k: 0 for k in sorted(ENTITY_TYPES)}
    layers = []
    current_entity = None
    current_layer = None
    entities = []
    closed_polyline_flags = []

    for code, value in pairs:
        if code == "0":
            if current_entity:
                entities.append({"type": current_entity, "layer": current_layer or "0"})
            current_entity = value if value in ENTITY_TYPES else None
            current_layer = None
            if value in entity_counts:
                entity_counts[value] += 1
        elif current_entity and code == "8":
            current_layer = value
            layers.append(value)
        elif current_entity in {"POLYLINE", "LWPOLYLINE"} and code == "70":
            try:
                closed_polyline_flags.append(bool(int(value) & 1))
            except ValueError:
                pass
    if current_entity:
        entities.append({"type": current_entity, "layer": current_layer or "0"})

    room_layers = sorted({e["layer"] for e in entities if e["layer"] not in {"0", "WALLS"}})
    polyline_count = entity_counts["POLYLINE"] + entity_counts["LWPOLYLINE"]
    closed_count = sum(closed_polyline_flags)

    return {
        "file": str(path),
        "bytes": path.stat().st_size,
        "entity_counts": entity_counts,
        "num_entities": sum(entity_counts.values()),
        "layers": sorted(set(layers)),
        "num_layers": len(set(layers)),
        "room_layers": room_layers,
        "num_room_layers": len(room_layers),
        "polyline_count": polyline_count,
        "closed_polyline_count": closed_count,
        "closed_polyline_rate": closed_count / polyline_count if polyline_count else 0.0,
        "has_wall_layer": "WALLS" in set(layers),
        "has_room_geometry": bool(room_layers and polyline_count),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--output-json", type=Path)
    args = ap.parse_args()

    files = []
    for path in args.paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.dxf")))
        elif path.suffix.lower() == ".dxf":
            files.append(path)
    if not files:
        raise SystemExit("No DXF files found")

    per_file = [validate_file(path) for path in files]
    summary = {
        "num_files": len(per_file),
        "export_success_rate": sum(r["has_room_geometry"] for r in per_file) / len(per_file),
        "mean_entities_per_file": mean(r["num_entities"] for r in per_file),
        "median_file_size_bytes": median(r["bytes"] for r in per_file),
        "mean_room_layers": mean(r["num_room_layers"] for r in per_file),
        "mean_closed_polyline_rate": mean(r["closed_polyline_rate"] for r in per_file),
        "files_with_wall_layer_rate": sum(r["has_wall_layer"] for r in per_file) / len(per_file),
    }
    output = {"summary": summary, "files": per_file}
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
