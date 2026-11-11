#!/usr/bin/env python3
"""Build a data-only offline carrier for the unchanged 學測 and 會考 template PDFs.

No executable attachments, question generation, template redrawing or ZIPs.
The knowledge-file manifest, not an attachment's name, remains the trust anchor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

from fetch_hosted_template_assets import CAP_MAP, DEFAULT_MAP, ROOT, verify


def attachment_name(subject: dict, asset: dict) -> str:
    return f"{subject['slug']}--{asset['component']}.pdf"


def build(output: Path, map_path: Path = DEFAULT_MAP) -> dict:
    maps = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (map_path, CAP_MAP) if path.is_file()]
    manifest = {"subjects": [s for m in maps for s in m["subjects"]]}
    expected = sum(m["asset_count"] for m in maps)
    doc = pymupdf.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_text((40, 35), "Taiwan Exam 離線模板資源", fontname="china-t", fontsize=17)
    page.insert_text((40, 55), "請連同最新版知識檔上傳至出卷對話，由 AI 取用當科模板。", fontname="china-t", fontsize=11)
    page.insert_text((40, 72), "本檔不是考卷或安裝程式；若平台移除附件，仍須回報限制。", fontname="china-t", fontsize=11)
    lines = ["Taiwan Exam - offline template resources", "",
             f"Data-only companion / {expected} unchanged PDF attachments",
             "Not a Skill installer, exam, or software archive.", "",
             "Use only if the generation runtime cannot download template files.",
             "Upload this PDF alongside the current Web Knowledge Markdown.",
             "The code/file runtime must read embedded PDF attachments (PyMuPDF).",
             "Extract only the requested subject; verify against the knowledge map.",
             "Reading this visible page alone does not load the template files.", "",
             "No JavaScript, launch actions, code, or font files are attached.", "",
             "Included subjects:"]
    count = 0
    for subject in manifest["subjects"]:
        lines.append(f"  {subject['slug']}: {len(subject['assets'])} PDF files")
        for asset in subject["assets"]:
            data = (ROOT / asset["repository_path"]).read_bytes()
            verify(asset, data)
            name = attachment_name(subject, asset)
            doc.embfile_add(name, data, filename=name, ufilename=name,
                            desc=f"Unchanged template; SHA-256 {asset['sha256']}")
            count += 1
    if count != expected or len(doc.embfile_names()) != expected:
        raise ValueError(f"Expected exactly {expected} unique PDF attachments")
    lines += ["", "Upstream: https://github.com/niansia/taiwan-exam",
              "Copyright (c) 2026 niansia. Project code/docs: MIT (see repository).",
              "Third-party materials retain their separate provenance.", "",
              "If a platform removes attachments, report that capability limit.",
              "Never rebuild a lookalike template or silently downgrade a full paper."]
    if page.insert_textbox(pymupdf.Rect(40, 92, 555, 810), "\n".join(lines),
                           fontname="helv", fontsize=11, lineheight=1.5) < 0:
        raise ValueError("Resource index overflow")
    doc.set_metadata({"title": "Taiwan Exam offline template resources",
                      "author": "niansia", "subject": f"{expected} unchanged PDF attachments; data only"})
    for xref in range(1, doc.xref_length()):
        if doc.xref_get_key(xref, "Type") == ("name", "/EmbeddedFile"):
            doc.xref_set_key(xref, "Params/CreationDate", "null")
            doc.xref_set_key(xref, "Params/ModDate", "null")
    output.parent.mkdir(parents=True, exist_ok=True)
    # No creation timestamps or random document IDs: stable inputs, stable bytes.
    data = doc.tobytes(garbage=4, deflate=True, no_new_id=True)
    doc.close()
    output.write_bytes(data)
    return {"path": str(output), "attachment_count": count, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
