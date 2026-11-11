#!/usr/bin/env python3
"""Hashed wording fingerprints of the official 113-115 會考 items, for originality checks.

Input: the folder build_cap_pack.py reads (one sub-folder per ROC year with the booklets).
Output: exam_packs/會考/metadata/official-item-fingerprints.json — for each official item,
32-bit hashes of the four-character CJK runs that occur in that item and in no other official
item. No text is stored; a run cannot be recovered from its hash. validate_cap_quality.py
flags a new item sharing OVERLAP_MIN of them with one official item (a hosted 會考社會 paper
rewrote 115's 「原料採取區域」 糖業 group without seeing it).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "exam_packs" / "會考" / "metadata" / "official-item-fingerprints.json"
FILES = {"會考國文": "chinese", "會考英語": "english", "會考數學": "math", "會考社會": "social", "會考自然": "science"}
CJK4 = re.compile(r"(?=([一-鿿]{4}))")


def gram_hash(gram: str) -> int:
    return int(hashlib.sha1(gram.encode("utf-8")).hexdigest()[:8], 16)


def grams(text: str) -> set[int]:
    return {gram_hash(g) for g in CJK4.findall(re.sub(r"\s", "", text))}


def official_items(path: Path) -> dict[int, str]:
    with pymupdf.open(path) as doc:
        text = "\n".join(page.get_text() for page in list(doc)[1:])
    parts = re.split(r"\n\s*(\d{1,2})\.\s*\n?", "\n" + re.sub(r"[  \t]+", " ", text))
    out: dict[int, str] = {}
    for i in range(1, len(parts) - 1, 2):
        n = int(parts[i])
        if n not in out and 1 <= n <= 60:
            out[n] = parts[i + 1]
    return out


def build(source: Path) -> dict:
    rows = []
    for subject, stem in FILES.items():
        for year in (113, 114, 115):
            path = source / str(year) / f"{stem}.pdf"
            if path.is_file():
                for number, text in official_items(path).items():
                    rows.append({"subject": subject, "year": year, "number": number, "grams": grams(text)})
    owners = defaultdict(int)
    for row in rows:
        for g in row["grams"]:
            owners[g] += 1
    items = [{"subject": r["subject"], "year": r["year"], "number": r["number"],
              "grams": sorted(g for g in r["grams"] if owners[g] == 1)} for r in rows]
    return {"schema_version": 1, "method": "sha1[:8] of 4-character CJK runs unique to one official 113-115 item",
            "overlap_min": 6, "items": [i for i in items if i["grams"]]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    data = build(args.source_dir)
    OUTPUT.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"items": len(data["items"]), "grams": sum(len(i["grams"]) for i in data["items"]),
                      "bytes": OUTPUT.stat().st_size}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
