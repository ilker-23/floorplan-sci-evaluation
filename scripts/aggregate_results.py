#!/usr/bin/env python3
"""Aggregate evaluation reports into manuscript-ready tables.

The tool combines per-model layout metrics, optional architectural screening,
and optional DXF validation into CSV and Markdown tables.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_nested(data: dict | None, path: list[str], default=None):
    cur = data
    if cur is None:
        return default
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def fmt(value, digits: int = 4) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def row_from_reports(model: str, layout: dict, arch: dict | None, dxf: dict | None) -> dict:
    return {
        "model": model,
        "n_eval": get_nested(layout, ["summary", "num_evaluated"]),
        "miou_mean": get_nested(layout, ["summary", "miou", "mean"]),
        "miou_std": get_nested(layout, ["summary", "miou", "std"]),
        "adj_precision_mean": get_nested(layout, ["summary", "adj_precision", "mean"]),
        "adj_recall_mean": get_nested(layout, ["summary", "adj_recall", "mean"]),
        "adj_f1_mean": get_nested(layout, ["summary", "adj_f1", "mean"]),
        "overlap_ratio_mean": get_nested(layout, ["summary", "overlap_ratio", "mean"]),
        "boundary_violation_ratio_mean": get_nested(layout, ["summary", "boundary_violation_ratio", "mean"]),
        "area_mape_mean": get_nested(layout, ["summary", "area_mape", "mean"]),
        "connectivity_valid_rate": get_nested(layout, ["summary", "connectivity_valid_rate"]),
        "miou_above_0_50": get_nested(layout, ["summary", "miou_above_0_50"]),
        "miou_above_0_70": get_nested(layout, ["summary", "miou_above_0_70"]),
        "level_1_screen_pass_rate": get_nested(arch, ["summary", "level_1_screen_pass_rate"]),
        "mean_warning_count": get_nested(arch, ["summary", "mean_warning_count"]),
        "dxf_files": get_nested(dxf, ["summary", "num_files"]),
        "dxf_export_success_rate": get_nested(dxf, ["summary", "export_success_rate"]),
        "dxf_closed_polyline_rate": get_nested(dxf, ["summary", "mean_closed_polyline_rate"]),
        "dxf_mean_room_layers": get_nested(dxf, ["summary", "mean_room_layers"]),
    }


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field) for field in fields} for row in rows])


def write_markdown(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("| " + " | ".join(["---"] * len(fields)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(field)) for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", required=True, help="Model name. Repeat for multiple models.")
    ap.add_argument("--layout", action="append", required=True, type=Path, help="Layout metric JSON. Repeat in same order as --model.")
    ap.add_argument("--architectural", action="append", type=Path, help="Optional architectural JSON. Repeat in same order or omit.")
    ap.add_argument("--dxf", action="append", type=Path, help="Optional DXF validation JSON. Repeat in same order or omit.")
    ap.add_argument("--output-csv", required=True, type=Path)
    ap.add_argument("--output-md", type=Path)
    args = ap.parse_args()

    n = len(args.model)
    if len(args.layout) != n:
        raise SystemExit("--model and --layout counts must match")
    if args.architectural and len(args.architectural) != n:
        raise SystemExit("--architectural count must match --model count")
    if args.dxf and len(args.dxf) != n:
        raise SystemExit("--dxf count must match --model count")

    rows = []
    for i, model in enumerate(args.model):
        layout = read_json(args.layout[i])
        arch = read_json(args.architectural[i]) if args.architectural else None
        dxf = read_json(args.dxf[i]) if args.dxf else None
        rows.append(row_from_reports(model, layout, arch, dxf))

    fields = [
        "model",
        "n_eval",
        "miou_mean",
        "miou_std",
        "adj_precision_mean",
        "adj_recall_mean",
        "adj_f1_mean",
        "overlap_ratio_mean",
        "boundary_violation_ratio_mean",
        "area_mape_mean",
        "connectivity_valid_rate",
        "level_1_screen_pass_rate",
        "dxf_export_success_rate",
        "dxf_closed_polyline_rate",
    ]
    write_csv(args.output_csv, rows, fields)
    if args.output_md:
        write_markdown(args.output_md, rows, fields)
    print(json.dumps({"rows": len(rows), "output_csv": str(args.output_csv), "output_md": str(args.output_md) if args.output_md else None}, indent=2))


if __name__ == "__main__":
    main()
