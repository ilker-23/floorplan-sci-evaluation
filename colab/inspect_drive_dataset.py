#!/usr/bin/env python3
"""Inspect a Google Drive dataset folder from Colab.

This does not convert the dataset. It inventories likely RPLAN/Graph2Plan files
so we can write the correct converter instead of guessing.
"""
from __future__ import annotations

import argparse
import json
import pickle
from collections import Counter, defaultdict
from pathlib import Path


TEXT_EXTS = {".json", ".jsonl", ".txt", ".csv", ".yaml", ".yml"}
DATA_EXTS = {".pkl", ".pickle", ".npy", ".npz", ".mat", ".h5", ".hdf5", ".json", ".jsonl"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}
CAD_EXTS = {".dxf", ".dwg"}


def safe_pickle_summary(path: Path) -> dict:
    try:
        with path.open("rb") as f:
            obj = pickle.load(f)
    except Exception as exc:
        return {"readable": False, "error": type(exc).__name__ + ": " + str(exc)[:200]}
    summary = {"readable": True, "type": type(obj).__name__}
    try:
        summary["len"] = len(obj)
    except Exception:
        pass
    if isinstance(obj, dict):
        summary["keys"] = [str(k) for k in list(obj.keys())[:20]]
    elif isinstance(obj, (list, tuple)) and obj:
        summary["first_type"] = type(obj[0]).__name__
        if isinstance(obj[0], dict):
            summary["first_keys"] = [str(k) for k in list(obj[0].keys())[:20]]
    return summary


def safe_json_summary(path: Path) -> dict:
    try:
        if path.suffix.lower() == ".jsonl":
            first = None
            count = 0
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    count += 1
                    if first is None:
                        first = json.loads(line)
            out = {"readable": True, "jsonl_rows": count, "first_type": type(first).__name__}
            if isinstance(first, dict):
                out["first_keys"] = list(first.keys())[:20]
            return out
        obj = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:
        return {"readable": False, "error": type(exc).__name__ + ": " + str(exc)[:200]}
    out = {"readable": True, "type": type(obj).__name__}
    try:
        out["len"] = len(obj)
    except Exception:
        pass
    if isinstance(obj, dict):
        out["keys"] = list(obj.keys())[:20]
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        out["first_keys"] = list(obj[0].keys())[:20]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--output-json", required=True, type=Path)
    ap.add_argument("--max-files", type=int, default=20000)
    args = ap.parse_args()

    if not args.root.exists():
        raise SystemExit(f"Root does not exist: {args.root}")

    files = []
    for idx, path in enumerate(args.root.rglob("*")):
        if idx > args.max_files:
            break
        if path.is_file():
            files.append(path)

    ext_counts = Counter(p.suffix.lower() or "<no_ext>" for p in files)
    dir_counts = Counter(str(p.parent.relative_to(args.root)) for p in files)
    candidates = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix in DATA_EXTS or suffix in CAD_EXTS:
            rel = str(path.relative_to(args.root))
            item = {"path": rel, "suffix": suffix, "bytes": path.stat().st_size}
            if suffix in {".pkl", ".pickle"}:
                item["summary"] = safe_pickle_summary(path)
            elif suffix in {".json", ".jsonl"}:
                item["summary"] = safe_json_summary(path)
            candidates.append(item)

    output = {
        "root": str(args.root),
        "num_files_seen": len(files),
        "extension_counts": dict(ext_counts.most_common()),
        "top_directories": dict(dir_counts.most_common(50)),
        "candidate_data_files": candidates[:500],
        "notes": [
            "Use this inventory to identify the actual RPLAN/Graph2Plan source file.",
            "Do not train final models until metadata/plans.jsonl and a frozen split exist.",
        ],
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2)[:12000])


if __name__ == "__main__":
    main()
