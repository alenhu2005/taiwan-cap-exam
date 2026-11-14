#!/usr/bin/env python3
"""What `append_items.py` does for a 會考 batch besides saving it.

A 54-item 會考社會 run (2026-11) spent hours on loops the tools could have closed: a 35 MB figure
PDF (a whole CJK font) slowed every proof, `check-figures` re-reported the whole paper's figures
after every batch, and 22 crop proofs were redone after the final layout moved every crop. For
each saved batch this module

* subsets the fonts of large figure PDFs in place (pixels and text verified) and updates the hash;
* checks only this batch's figures and writes a print-size PNG preview of each, so a figure is
  looked at once, while it is fresh, without proofing the page around it;
* keeps the per-item review book (`cap_review_book.py`) in step with the saved items.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf

SHRINK_ABOVE_BYTES = 1_500_000
PREVIEW_DIR = "figure-previews"
BODY_WIDTH_PT = 460


def _assets(record: dict):
    """(owner, key, asset) for every file a question or answer references."""
    visual = record.get("visual_asset")
    if isinstance(visual, dict) and visual.get("path"):
        yield "figure", None, visual
    for key, asset in (record.get("inline_assets") or {}).items():
        if isinstance(asset, dict) and asset.get("path"):
            yield "inline", key, asset


def _same_pages(before: bytes, after: bytes) -> bool:
    with pymupdf.open(stream=before, filetype="pdf") as a, pymupdf.open(stream=after, filetype="pdf") as b:
        if len(a) != len(b):
            return False
        for pa, pb in zip(a, b):
            if pa.get_text() != pb.get_text():
                return False
            if pa.get_pixmap(alpha=False).samples != pb.get_pixmap(alpha=False).samples:
                return False
    return True


def shrink_figures(root: Path, records: list[dict]) -> list[dict]:
    """Subset the embedded fonts of large figure PDFs in place; update each referencing sha256."""
    shrunk, done = [], {}
    for record in records:
        for _, _, asset in _assets(record):
            path = (root / str(asset["path"])).resolve()
            if path in done:
                if done[path]:
                    asset["sha256"] = done[path]
                continue
            done[path] = None
            if path.suffix.lower() != ".pdf" or not path.is_file() or path.stat().st_size <= SHRINK_ABOVE_BYTES:
                continue
            before = path.read_bytes()
            if asset.get("sha256") and hashlib.sha256(before).hexdigest() != asset["sha256"]:
                continue   # the saved hash names other bytes; authoring checks report it
            try:
                with pymupdf.open(stream=before, filetype="pdf") as doc:
                    doc.subset_fonts()
                    after = doc.tobytes(garbage=4, deflate=True, no_new_id=True)
                if len(after) >= len(before) or not _same_pages(before, after):
                    continue
            except Exception:  # noqa: BLE001 - keep the author's file whenever the subsetter fails
                continue
            path.write_bytes(after)
            digest = hashlib.sha256(after).hexdigest()
            done[path] = digest
            asset["sha256"] = digest
            shrunk.append({"path": str(asset["path"]), "bytes_before": len(before), "bytes_after": len(after)})
    return shrunk


def preview_figures(root: Path, records: list[dict]) -> list[str]:
    """A PNG of each figure at its printed width (150 dpi), for looking at the art once, now."""
    out_dir = root / PREVIEW_DIR
    previews = []
    for record in records:
        for owner, key, asset in _assets(record):
            path = (root / str(asset["path"])).resolve()
            if not path.is_file():
                continue
            width = asset.get("width_pt") if owner == "inline" else BODY_WIDTH_PT * float(asset.get("width_percent", 62)) / 100
            try:
                with pymupdf.open(path) as doc:
                    page = doc[0]
                    scale = float(width) / page.rect.width * 150 / 72
                    out_dir.mkdir(exist_ok=True)
                    target = out_dir / f"{record.get('id') or record.get('question_id')}-{key or 'figure'}.png"
                    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).save(target)
                    previews.append(str(target.relative_to(root)))
            except Exception:  # noqa: BLE001 - unreadable art is reported by the figure check
                continue
    return previews


def batch_figure_check(root: Path, exam: dict, ids: set[str]) -> dict:
    """The figure self-check on this batch's items only (the whole paper is checked once before plan)."""
    from hosted_evidence_refresh import figure_selfcheck
    from run_hosted_workflow import asset_issues
    subset = {**exam, "questions": [q for q in exam.get("questions") or [] if q.get("id") in ids],
              "answers": [a for a in exam.get("answers") or [] if a.get("question_id") in ids]}
    result = figure_selfcheck(root, subset, asset_issues=asset_issues)
    return {"errors": result.get("errors"), "warnings": result.get("warnings"),
            "figures": [f for f in result.get("figures") or [] if f.get("errors") or f.get("warnings")]}
