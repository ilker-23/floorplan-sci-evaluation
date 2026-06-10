#!/usr/bin/env python3
"""Find risky manuscript claims that require strong evidence."""
from __future__ import annotations

import argparse
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


RISKY_PATTERNS = [
    r"\bconstructible\b",
    r"\bcode[- ]conformant\b",
    r"\bcode[- ]compliant\b",
    r"\bdrafting[- ]ready\b",
    r"\bCAD[- ]ready\b",
    r"\bseismic\b",
    r"\bdeploy(?:ment)?[- ]ready\b",
    r"\bguarantee[sd]?\b",
    r"\bby construction\b",
    r"\bproves?\b",
    r"\bdemonstrates? superiority\b",
    r"\bstate[- ]of[- ]the[- ]art\b",
]


def read_docx(path: Path) -> str:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    texts = []
    for t in root.iter("{%s}t" % ns["w"]):
        texts.append(t.text or "")
    return " ".join(texts)


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return read_docx(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()

    combined = []
    for path in args.paths:
        text = read_text(path)
        for pattern in RISKY_PATTERNS:
            rx = re.compile(pattern, re.IGNORECASE)
            for match in rx.finditer(text):
                start = max(0, match.start() - 90)
                end = min(len(text), match.end() + 120)
                context = " ".join(text[start:end].split())
                combined.append((str(path), pattern, context))

    if not combined:
        print("No risky claim patterns found.")
        return

    for path, pattern, context in combined:
        print(f"\n[{path}] pattern={pattern}")
        print(context)


if __name__ == "__main__":
    main()
