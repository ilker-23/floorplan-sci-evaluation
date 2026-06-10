#!/usr/bin/env python3
"""Deep-inspect Graph2Plan/RPLAN .pkl/.mat/.npz records.

Use this after `inspect_drive_dataset.py` identifies candidate files. The goal is
to reveal the nested structure of `data_train_converted.pkl`,
`data_test_converted.pkl`, or MAT files before writing a converter.
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path


def load_any(path: Path):
    suffix = path.suffix.lower()
    if suffix in {".pkl", ".pickle"}:
        with path.open("rb") as f:
            return pickle.load(f)
    if suffix == ".npz":
        import numpy as np

        return dict(np.load(path, allow_pickle=True))
    if suffix == ".npy":
        import numpy as np

        return np.load(path, allow_pickle=True)
    if suffix == ".mat":
        try:
            from scipy.io import loadmat
        except Exception as exc:
            raise SystemExit("scipy is required for .mat inspection") from exc
        return loadmat(path, squeeze_me=False, struct_as_record=False)
    raise SystemExit(f"Unsupported file type: {path.suffix}")


def short_scalar(value):
    text = repr(value)
    return text[:160] + ("..." if len(text) > 160 else "")


def summarize(obj, depth: int = 0, max_depth: int = 4, max_items: int = 8):
    out = {"type": type(obj).__name__}

    shape = getattr(obj, "shape", None)
    dtype = getattr(obj, "dtype", None)
    if shape is not None:
        out["shape"] = list(shape)
    if dtype is not None:
        out["dtype"] = str(dtype)

    if depth >= max_depth:
        out["truncated"] = True
        return out

    if isinstance(obj, dict):
        keys = list(obj.keys())
        out["len"] = len(keys)
        out["keys"] = [str(k) for k in keys[:max_items]]
        out["items"] = {
            str(k): summarize(obj[k], depth + 1, max_depth, max_items)
            for k in keys[:max_items]
        }
        return out

    if isinstance(obj, (list, tuple)):
        out["len"] = len(obj)
        out["items"] = [
            summarize(item, depth + 1, max_depth, max_items)
            for item in list(obj)[:max_items]
        ]
        return out

    # scipy mat_struct objects expose _fieldnames.
    fieldnames = getattr(obj, "_fieldnames", None)
    if fieldnames:
        out["fields"] = [str(f) for f in fieldnames[:max_items]]
        out["items"] = {
            str(f): summarize(getattr(obj, f), depth + 1, max_depth, max_items)
            for f in fieldnames[:max_items]
        }
        return out

    # numpy arrays may contain objects. Inspect a few elements safely.
    if shape is not None:
        try:
            flat = obj.ravel()
            out["len"] = int(flat.shape[0])
            out["items"] = [
                summarize(flat[i].item() if hasattr(flat[i], "item") else flat[i], depth + 1, max_depth, max_items)
                for i in range(min(max_items, flat.shape[0]))
            ]
        except Exception as exc:
            out["array_item_error"] = type(exc).__name__ + ": " + str(exc)[:120]
        return out

    if isinstance(obj, (str, int, float, bool)) or obj is None:
        out["value"] = short_scalar(obj)
        return out

    try:
        out["repr"] = short_scalar(obj)
    except Exception:
        pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, type=Path)
    ap.add_argument("--output-json", required=True, type=Path)
    ap.add_argument("--max-depth", type=int, default=5)
    ap.add_argument("--max-items", type=int, default=10)
    args = ap.parse_args()

    obj = load_any(args.file)
    summary = {
        "file": str(args.file),
        "bytes": args.file.stat().st_size,
        "summary": summarize(obj, max_depth=args.max_depth, max_items=args.max_items),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False)[:20000])


if __name__ == "__main__":
    main()
