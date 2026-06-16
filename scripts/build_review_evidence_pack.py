#!/usr/bin/env python3
"""Build a reviewer-facing evidence pack from layout metric JSON files.

This tool is intentionally stricter than a normal results aggregator. It marks
oracle, ground-truth-spatial, and other diagnostic runs as non-final evidence and
checks whether a candidate model actually beats the declared baseline under
review-relevant validity gates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


METRIC_COLUMNS = [
    "name",
    "role",
    "n_eval",
    "miou",
    "adj_f1",
    "overlap_excess",
    "boundary",
    "area_mape",
    "connectivity",
    "delta_vs_reference",
    "verdict",
]


def parse_name_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Expected NAME=PATH")
    name, path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("Run name cannot be empty")
    return name, Path(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def unwrap_summary(data: dict) -> dict:
    if isinstance(data.get("summary"), dict):
        return data["summary"]
    return data


def mean_metric(summary: dict, key: str):
    value = summary.get(key)
    if isinstance(value, dict):
        return value.get("mean")
    return value


def number_or_none(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value, digits: int = 4) -> str:
    if value is None:
        return "NA"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def infer_role(name: str, explicit_diagnostic: set[str], explicit_baseline: set[str]) -> str:
    lower = name.lower()
    if name in explicit_diagnostic:
        return "diagnostic"
    if name in explicit_baseline:
        return "baseline"
    diagnostic_terms = ["oracle", "gt_copy", "spatial_gt", "spatial-from-gt", "leak", "upper"]
    if any(term in lower for term in diagnostic_terms):
        return "diagnostic"
    baseline_terms = ["baseline", "nearest", "template", "median"]
    if any(term in lower for term in baseline_terms):
        return "baseline"
    return "candidate"


def extract_row(name: str, path: Path, role: str) -> dict:
    summary = unwrap_summary(read_json(path))
    return {
        "name": name,
        "path": str(path),
        "role": role,
        "n_eval": summary.get("num_evaluated"),
        "miou": number_or_none(mean_metric(summary, "miou")),
        "adj_f1": number_or_none(mean_metric(summary, "adj_f1")),
        "overlap_excess": number_or_none(mean_metric(summary, "overlap_excess_ratio")),
        "boundary": number_or_none(mean_metric(summary, "boundary_violation_ratio")),
        "area_mape": number_or_none(mean_metric(summary, "area_mape")),
        "connectivity": number_or_none(summary.get("connectivity_valid_rate")),
        "gt_overlap": number_or_none(mean_metric(summary, "gt_overlap_ratio")),
        "raw_summary_keys": sorted(summary.keys()),
    }


def review_verdict(row: dict, reference_miou: float | None) -> str:
    if row["role"] == "diagnostic":
        return "diagnostic only"
    n_eval = row.get("n_eval") or 0
    miou = row.get("miou")
    overlap = row.get("overlap_excess")
    boundary = row.get("boundary")
    adj_f1 = row.get("adj_f1")
    connectivity = row.get("connectivity")
    if miou is None:
        return "incomplete"
    if n_eval < 1000:
        return "not final: small/partial test"
    if reference_miou is not None and miou < reference_miou:
        return "weak: below reference baseline"
    if boundary is not None and boundary > 0.01:
        return "risky: boundary failures"
    if overlap is not None and overlap > 0.05:
        return "risky: excess overlap"
    if adj_f1 is not None and adj_f1 < 0.20:
        return "risky: weak topology"
    if connectivity is not None and connectivity < 0.50:
        return "risky: low connectivity"
    if reference_miou is not None and miou >= reference_miou + 0.02:
        return "candidate evidence"
    return "borderline"


def markdown_table(rows: list[dict]) -> str:
    lines = []
    lines.append("| " + " | ".join(METRIC_COLUMNS) + " |")
    lines.append("| " + " | ".join(["---"] * len(METRIC_COLUMNS)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(col)) for col in METRIC_COLUMNS) + " |")
    return "\n".join(lines)


def build_markdown(rows: list[dict], reference_name: str | None) -> str:
    lines = [
        "# Q1 Reviewer Evidence Pack",
        "",
        "This pack separates final candidate evidence from baselines and diagnostic runs. Diagnostic runs, including oracle copies and ground-truth-spatial-edge variants, must not be reported as final model performance.",
        "",
    ]
    if reference_name:
        lines.append(f"Reference baseline: `{reference_name}`.")
        lines.append("")
    lines.append(markdown_table(rows))
    lines.append("")
    lines.append("## Reviewer Gates")
    lines.append("")
    lines.append("- A final model must be leakage-free and evaluated on the held-out test split.")
    lines.append("- A final model should beat the declared in-house baseline under the same split and metrics.")
    lines.append("- High mIoU is not enough if excess overlap, boundary failures, topology, or connectivity collapse.")
    lines.append("- Oracle and GT-spatial-edge runs are sanity checks or leakage diagnostics, not model claims.")
    lines.append("")
    lines.append("## Manuscript Use")
    lines.append("")
    lines.append("Use the `candidate evidence` rows in the main results table. Put diagnostic rows in an ablation or threat-to-validity paragraph, with explicit wording that they are not leakage-free final results.")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, type=parse_name_path, help="Run as NAME=metrics.json. Repeat for multiple runs.")
    ap.add_argument("--reference", help="Run name to use as the baseline reference for deltas.")
    ap.add_argument("--diagnostic", action="append", default=[], help="Run name that must be treated as diagnostic-only.")
    ap.add_argument("--baseline", action="append", default=[], help="Run name that must be treated as an in-house baseline.")
    ap.add_argument("--output-md", required=True, type=Path)
    ap.add_argument("--output-json", type=Path)
    args = ap.parse_args()

    diagnostic = set(args.diagnostic)
    baseline = set(args.baseline)
    rows = []
    for name, path in args.run:
        role = infer_role(name, diagnostic, baseline)
        rows.append(extract_row(name, path, role))

    reference_miou = None
    if args.reference:
        ref_rows = [r for r in rows if r["name"] == args.reference]
        if not ref_rows:
            raise SystemExit(f"Reference run not found: {args.reference}")
        reference_miou = ref_rows[0].get("miou")

    for row in rows:
        miou = row.get("miou")
        row["delta_vs_reference"] = None if miou is None or reference_miou is None else miou - reference_miou
        row["verdict"] = review_verdict(row, reference_miou)

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(build_markdown(rows, args.reference), encoding="utf-8")

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps({"reference": args.reference, "rows": rows}, indent=2), encoding="utf-8")

    print(json.dumps({"rows": len(rows), "output_md": str(args.output_md), "output_json": str(args.output_json) if args.output_json else None}, indent=2))


if __name__ == "__main__":
    main()
