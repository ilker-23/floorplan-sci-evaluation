#!/usr/bin/env python3
"""Smoke tests for the SCI evaluation command-line tools."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"


def run_cmd(args: list[str]) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_layout_metrics(tmp: Path) -> None:
    out = tmp / "layout_metrics.json"
    by_room = tmp / "by_room.csv"
    run_cmd(
        [
            sys.executable,
            "scripts/evaluate_layout_metrics.py",
            "--ground-truth",
            str(FIX / "layout_gt.jsonl"),
            "--predictions",
            str(FIX / "layout_pred.jsonl"),
            "--output-json",
            str(out),
            "--by-room-count-csv",
            str(by_room),
            "--contact-tol",
            "0.025",
        ]
    )
    summary = read_json(out)["summary"]
    assert summary["num_evaluated"] == 2
    assert 0.85 < summary["miou"]["mean"] <= 1.0
    assert summary["adj_f1"]["mean"] >= 0.5
    assert "gt_overlap_ratio" in summary
    assert "overlap_excess_ratio" in summary
    assert "oracle_like_warning" in summary
    assert by_room.exists()


def test_architectural_rules(tmp: Path) -> None:
    out = tmp / "architectural_rules.json"
    run_cmd(
        [
            sys.executable,
            "scripts/evaluate_architectural_rules.py",
            "--layouts",
            str(FIX / "layout_pred.jsonl"),
            "--rules",
            "configs/architectural_rules.example.json",
            "--output-json",
            str(out),
        ]
    )
    summary = read_json(out)["summary"]
    assert summary["num_plans"] == 2
    assert 0.0 <= summary["level_1_screen_pass_rate"] <= 1.0


def test_dxf_validation(tmp: Path) -> None:
    out = tmp / "dxf.json"
    run_cmd(
        [
            sys.executable,
            "scripts/validate_dxf.py",
            str(FIX / "dxf"),
            "--output-json",
            str(out),
        ]
    )
    summary = read_json(out)["summary"]
    assert summary["num_files"] == 1
    assert summary["export_success_rate"] == 1.0
    assert summary["mean_closed_polyline_rate"] == 1.0


def test_split_generation(tmp: Path) -> None:
    out_dir = tmp / "splits"
    run_cmd(
        [
            sys.executable,
            "scripts/make_splits.py",
            "--input",
            str(FIX / "metadata.jsonl"),
            "--output-dir",
            str(out_dir),
            "--seed",
            "42",
        ]
    )
    manifest = read_json(out_dir / "split_manifest.json")
    assert manifest["num_plans"] == 4
    assert manifest["counts"]["train"] == 2
    assert manifest["counts"]["val"] == 1
    assert manifest["counts"]["test"] == 1
    assert (out_dir / "split_assignments.csv").exists()


def test_filter_by_split(tmp: Path) -> None:
    out_dir = tmp / "filtered"
    run_cmd(
        [
            sys.executable,
            "scripts/filter_layout_jsonl_by_split.py",
            "--input",
            str(FIX / "layout_gt.jsonl"),
            "--split-assignments",
            str(FIX / "split_assignments.csv"),
            "--output-dir",
            str(out_dir),
            "--strict",
        ]
    )
    test_gt = out_dir / "test_ground_truth.jsonl"
    assert test_gt.exists()
    assert len(test_gt.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_aggregate_results(tmp: Path) -> None:
    layout = tmp / "layout_metrics.json"
    arch = tmp / "architectural_rules.json"
    dxf = tmp / "dxf.json"
    csv_out = tmp / "summary.csv"
    md_out = tmp / "summary.md"
    run_cmd(
        [
            sys.executable,
            "scripts/evaluate_layout_metrics.py",
            "--ground-truth",
            str(FIX / "layout_gt.jsonl"),
            "--predictions",
            str(FIX / "layout_pred.jsonl"),
            "--output-json",
            str(layout),
            "--contact-tol",
            "0.025",
        ]
    )
    run_cmd(
        [
            sys.executable,
            "scripts/evaluate_architectural_rules.py",
            "--layouts",
            str(FIX / "layout_pred.jsonl"),
            "--rules",
            "configs/architectural_rules.example.json",
            "--output-json",
            str(arch),
        ]
    )
    run_cmd(
        [
            sys.executable,
            "scripts/validate_dxf.py",
            str(FIX / "dxf"),
            "--output-json",
            str(dxf),
        ]
    )
    run_cmd(
        [
            sys.executable,
            "scripts/aggregate_results.py",
            "--model",
            "fixture-model",
            "--layout",
            str(layout),
            "--architectural",
            str(arch),
            "--dxf",
            str(dxf),
            "--output-csv",
            str(csv_out),
            "--output-md",
            str(md_out),
        ]
    )
    assert "fixture-model" in csv_out.read_text(encoding="utf-8")
    assert "fixture-model" in md_out.read_text(encoding="utf-8")


def test_layout_schema_validation(tmp: Path) -> None:
    out = tmp / "schema.json"
    run_cmd(
        [
            sys.executable,
            "scripts/validate_layout_jsonl.py",
            "--input",
            str(FIX / "layout_gt.jsonl"),
            "--output-json",
            str(out),
        ]
    )
    summary = read_json(out)
    assert summary["valid"] is True
    assert summary["num_records"] == 2
    assert summary["min_rooms"] == 3


def test_prediction_set_validation(tmp: Path) -> None:
    out = tmp / "prediction_set.json"
    run_cmd(
        [
            sys.executable,
            "scripts/validate_prediction_set.py",
            "--ground-truth",
            str(FIX / "layout_gt.jsonl"),
            "--predictions",
            str(FIX / "layout_pred.jsonl"),
            "--split-assignments",
            str(FIX / "split_assignments.csv"),
            "--split",
            "test",
            "--output-json",
            str(out),
        ]
    )
    summary = read_json(out)
    assert summary["valid"] is True
    assert summary["num_expected"] == 2
    assert summary["num_missing_predictions"] == 0


def test_nearest_neighbor_baseline(tmp: Path) -> None:
    pred = tmp / "nn_baseline.jsonl"
    summary_path = tmp / "nn_baseline_summary.json"
    validation = tmp / "nn_baseline_validation.json"
    metrics = tmp / "nn_baseline_metrics.json"
    run_cmd(
        [
            sys.executable,
            "scripts/make_nearest_neighbor_baseline.py",
            "--input",
            str(FIX / "nn_baseline_layouts.jsonl"),
            "--split-assignments",
            str(FIX / "nn_baseline_splits.csv"),
            "--output-jsonl",
            str(pred),
            "--output-summary",
            str(summary_path),
        ]
    )
    baseline_summary = read_json(summary_path)
    assert baseline_summary["num_targets"] == 1
    assert baseline_summary["num_candidates"] == 2
    assert baseline_summary["exact_type_histogram_match_rate"] == 1.0
    run_cmd(
        [
            sys.executable,
            "scripts/validate_prediction_set.py",
            "--ground-truth",
            str(FIX / "nn_baseline_layouts.jsonl"),
            "--predictions",
            str(pred),
            "--split-assignments",
            str(FIX / "nn_baseline_splits.csv"),
            "--split",
            "test",
            "--allow-extra-predictions",
            "--output-json",
            str(validation),
        ]
    )
    assert read_json(validation)["valid"] is True
    run_cmd(
        [
            sys.executable,
            "scripts/evaluate_layout_metrics.py",
            "--ground-truth",
            str(FIX / "nn_baseline_layouts.jsonl"),
            "--predictions",
            str(pred),
            "--output-json",
            str(metrics),
        ]
    )
    assert read_json(metrics)["summary"]["num_evaluated"] == 1


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_layout_schema_validation(tmp)
        test_prediction_set_validation(tmp)
        test_nearest_neighbor_baseline(tmp)
        test_layout_metrics(tmp)
        test_architectural_rules(tmp)
        test_dxf_validation(tmp)
        test_split_generation(tmp)
        test_filter_by_split(tmp)
        test_aggregate_results(tmp)
    print("smoke tests passed")


if __name__ == "__main__":
    main()
