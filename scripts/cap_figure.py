#!/usr/bin/env python3
"""Shrink a figure PDF before it goes into an item: keep only the glyphs it draws.

  python scripts/cap_figure.py subset figures/q12.pdf --output figures/q12-small.pdf

A figure drawn with the full TW-Sung/TW-Kai font embedded weighed 18 MB. MuPDF's own subsetter
needs no extra package; the result is kept only if the page renders identically.
SVG tips: write subscripts as <tspan baseline-shift="sub" font-size="70%">1</tspan> (the body
fonts have no ₁₂ glyphs); give labels that cross lines a white halo with
style="paint-order:stroke;stroke:#fff;stroke-width:3px"; label in Chinese; draw in black and grey.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pymupdf


def subset(source: Path, output: Path) -> dict:
    data = source.read_bytes()
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        before = [p.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).samples for p in doc]
        doc.subset_fonts()
        small = doc.tobytes(garbage=4, deflate=True)
    with pymupdf.open(stream=small, filetype="pdf") as check:
        same = [p.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).samples for p in check] == before
    kept = small if same and len(small) < len(data) else data
    output.write_bytes(kept)
    return {"status": "subset" if kept is small else "unchanged", "bytes_before": len(data), "bytes_after": len(kept),
            "note": "record the new file's sha256 in the item's visual_asset"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("subset"); s.add_argument("source", type=Path); s.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(subset(args.source, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
