#!/usr/bin/env python3
"""Build the 115-form 會考 layout-only PDF assets and their hosted template map.

Run `python scripts/render_cap_template_assets.py --build-all` after changing
`cap_115_templates.py`. It prints every subject's components with the browser,
measures the dynamic-field boxes on the printed PDFs and rewrites
`exam_packs/會考/templates/115/hosted-web-template-assets.json`. It never
creates questions.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import pymupdf

from cap_115_templates import (BODY_BOX, EXAM, PACK_ROOT, PAGE_H, PAGE_W, ROOT, SUBJECT_ORDER, SUBJECTS,
                               WRITING_BODY_BOX, cover_markup, document, footer_box, formula_markup,
                               inner_markup, template_key)
from render_pdf import find_browser
from safe_rendering import browser_flags, prepare_html

MAP_PATH = PACK_ROOT / "hosted-web-template-assets.json"
# 會考 assets are published with this derivative distribution (學測 assets stay upstream).
REPOSITORY = "https://github.com/alenhu2005/taiwan-cap-exam"
RAW_ROOT = "https://raw.githubusercontent.com/alenhu2005/taiwan-cap-exam/main/"
VIEW_ROOT = REPOSITORY + "/blob/main/"
TREE_ROOT = REPOSITORY + "/tree/main/"
PACK_ID = "cap-115-layout-assets-v1"


def components(subject: str) -> dict[str, str]:
    """{component: page markup} for one subject; order is the review packet's page order."""
    parts = {"cover-blank": cover_markup(subject),
             "inner-odd-blank": inner_markup(subject),
             "inner-even-blank": inner_markup(subject)}
    if subject != "寫作測驗":
        parts["inner-even-turn-blank"] = inner_markup(subject, turn=True)
    if SUBJECTS[subject].get("formula"):
        parts["formula-blank"] = inner_markup(subject, body=formula_markup())
    return parts


# The pinned TW-Kai / TW-Sung fonts (prepare_hosted_run downloads the same files) replace the
# 115 booklets' 標楷體 / 細明體. Without them Chrome falls back to a system Kai face that it may
# embed as Type3 glyphs (1 MB per cover); subsets embed as compact outline fonts.
FONT_FAMILIES = {"kai": "DFKai-SB", "sung": "DFLiSong"}


def font_faces(markup: str, fonts: dict[str, Path]) -> str:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    text = html.unescape(re.sub(r"<[^>]+>", "", markup)) + "0123456789"
    rules = []
    for key, path in fonts.items():
        font = TTFont(str(path))
        options = subset.Options()
        options.layout_features = ["*"]
        subsetter = subset.Subsetter(options)
        subsetter.populate(text=text)
        subsetter.subset(font)
        buffer = io.BytesIO()
        font.save(buffer)
        data = base64.b64encode(buffer.getvalue()).decode()
        rules.append(f'@font-face {{font-family:"{FONT_FAMILIES[key]}";src:url(data:font/ttf;base64,{data})}}')
    return "\n".join(rules)


def _print_pdf(browser: Path, markup: str, output: Path, fonts: dict[str, Path] | None = None) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cap-115-template-") as temp:
        work = Path(temp)
        html_path = work / "template.html"
        runtime = work / "runtime"
        runtime.mkdir()
        prepared = prepare_html(document(markup, title=output.stem))
        if fonts:
            # Fixed, self-authored template markup: only this builder adds inline data: fonts.
            prepared = prepared.replace("default-src 'none';", "default-src 'none'; font-src data:;", 1)
            prepared = prepared.replace("</head>", f"<style>{font_faces(markup, fonts)}</style></head>", 1)
        html_path.write_text(prepared, encoding="utf-8")
        completed = subprocess.run(
            [str(browser), *browser_flags(runtime), "--no-pdf-header-footer",
             f"--print-to-pdf={output}", html_path.as_uri()],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        if not output.is_file() or output.stat().st_size < 1000:
            raise RuntimeError(completed.stderr or completed.stdout or "PDF輸出失敗")


def _extract_page(source: Path, index: int, output: Path) -> None:
    with pymupdf.open(source) as doc, pymupdf.open() as single:
        single.insert_pdf(doc, from_page=index, to_page=index)
        single.save(output, garbage=4, deflate=True)


def _chars(page) -> list[dict]:
    return [c for b in page.get_text("rawdict")["blocks"] for l in b.get("lines", [])
            for s in l["spans"] for c in s["chars"] if c["c"].strip()]


def _text_rect(page, needle: str, *, topmost: bool = False) -> pymupdf.Rect:
    """The run of glyphs spelling `needle`, from glyph origins (Type3 glyph boxes jitter)."""
    chars = _chars(page)
    text = "".join(c["c"] for c in chars)
    start = text.find(needle)
    if start < 0 or (not topmost and text.find(needle, start + 1) >= 0):
        raise ValueError(f"cover anchor {needle!r} not found exactly once")
    if topmost:
        starts = [i for i in range(len(text)) if text.startswith(needle, i)]
        start = min(starts, key=lambda i: chars[i]["origin"][1])
    run = chars[start:start + len(needle)]
    baseline = run[0]["origin"][1]
    size = run[0]["bbox"][3] - run[0]["bbox"][1]
    return pymupdf.Rect(run[0]["origin"][0], baseline - 11.5, run[-1]["bbox"][2], baseline + 2.5)


def cover_fields(path: Path, subject: str) -> dict:
    """Title band and the empty page/item slots, measured on the printed cover."""
    with pymupdf.open(path) as doc:
        page = doc[0]
        title_top = _text_rect(page, "TaiwanExam").y1 + 2
        subject_top = _text_rect(page, SUBJECTS[subject]["title"], topmost=True).y0 - 2
        # The title line sits where 115 prints 「115 年國中教育會考」 (y 51-87).
        fields = {"cover_title": [70.0, title_top + 6, PAGE_W - 70.0, min(subject_top, title_top + 46)]}
        if subject == "寫作測驗":
            return fields
        pages_left = _text_rect(page, "採雙面印刷，共")
        pages_right = _text_rect(page, "頁，第一部分有" if subject == "數學" else "頁，有")
        right = _text_rect(page, "題選擇題，第二部分" if subject == "數學" else "題選擇題，每題")
        if abs(right.y0 - pages_right.y0) > 3:   # the count opens the next line (數學, 英語)
            items = [right.x0 - 18.5, right.y0, right.x0 - .5, right.y1]
        else:
            items = [pages_right.x1 + .5, pages_right.y0, right.x0 - .5, pages_right.y1]
        fields["cover_pages"] = [pages_left.x1 + .5, pages_left.y0, pages_right.x0 - .5, pages_left.y1]
        fields["cover_items"] = items
    for key in ("cover_pages", "cover_items"):
        x0, y0, x1, y1 = fields[key]
        if not 12 <= x1 - x0 <= 30:
            raise ValueError(f"{subject} {key} slot is {x1 - x0:.1f} pt wide")
    return fields


def overlay_geometry(asset_dir: Path, subject: str) -> dict:
    body = WRITING_BODY_BOX if subject == "寫作測驗" else BODY_BOX
    geometry = {"body": list(body), **cover_fields(asset_dir / "cover-blank.pdf", subject)}
    footer = footer_box(subject)
    for parity in ("odd", "even"):
        geometry[parity] = {"footer": list(footer)} if footer else {}
    return geometry


def file_record(path: Path) -> dict:
    relative = path.relative_to(ROOT).as_posix()
    data = path.read_bytes()
    with pymupdf.open(path) as doc:
        pages = len(doc)
    return {"component": path.stem, "repository_path": relative,
            "download_url": RAW_ROOT + quote(relative, safe="/"), "view_url": VIEW_ROOT + quote(relative, safe="/"),
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "pages": pages}


def validate_packet(path: Path, subject: str) -> None:
    with pymupdf.open(path) as doc:
        expected = len(components(subject))
        if len(doc) != expected:
            raise ValueError(f"{subject}模板封包應為{expected}頁，實際為{len(doc)}頁")
        for index, page in enumerate(doc):
            if abs(page.rect.width - PAGE_W) > 1 or abs(page.rect.height - PAGE_H) > 1:
                raise ValueError(f"{subject}模板第{index + 1}頁不是A4")
        text = "".join(page.get_text() for page in doc)
        if "115 年國中教育會考" in text or "115年國中教育會考" in text:
            raise ValueError(f"{subject}空白模板殘留參考年度")
        if SUBJECTS[subject]["title"] not in doc[0].get_text():
            raise ValueError(f"{subject}封面缺少科目名稱")
        frames = [d["rect"] for d in doc[0].get_drawings() if d.get("rect") and d["rect"].width > 400]
        if len(frames) < 2:
            raise ValueError(f"{subject}封面缺少說明外框")
        if subject != "寫作測驗" and "請翻頁繼續作答" not in doc[3].get_text():
            raise ValueError(f"{subject}缺少翻頁提示頁")
        if SUBJECTS[subject].get("formula") and "一元二次方程式" not in doc[-1].get_text():
            raise ValueError("數學參考公式頁不完整")


def build_subject(browser: Path, subject: str, output_root: Path, fonts: dict[str, Path] | None = None) -> list[Path]:
    folder = output_root / SUBJECTS[subject]["slug"]
    parts = components(subject)
    packet = folder / "blank-template.pdf"
    _print_pdf(browser, "".join(parts.values()), packet, fonts)
    validate_packet(packet, subject)
    outputs = [packet]
    for index, name in enumerate(parts):
        path = folder / f"{name}.pdf"
        _extract_page(packet, index, path)
        outputs.append(path)
    # 115 會考 inner pages carry no running header, so odd and even pages are the same layer:
    # ship identical bytes (the Skill ZIP stores identical files once).
    (folder / "inner-even-blank.pdf").write_bytes((folder / "inner-odd-blank.pdf").read_bytes())
    return outputs


def build_map(output_root: Path = PACK_ROOT / "assets") -> dict:
    subjects, total = [], 0
    for subject in SUBJECT_ORDER:
        config = SUBJECTS[subject]
        asset_dir = output_root / config["slug"]
        wanted = [name for name in components(subject)]
        assets = [file_record(asset_dir / f"{name}.pdf") for name in ["blank-template", *wanted]]
        total += len(assets)
        subjects.append({
            "subject": template_key(subject), "exam": EXAM, "exam_subject": subject, "slug": config["slug"],
            "github_folder_url": TREE_ROOT + quote(asset_dir.relative_to(ROOT).as_posix(), safe="/"),
            "layout_profile": f'{config["slug"]}-115-measured-v1',
            "formula_variant": "cap-math" if config.get("formula") else None,
            "production_components": wanted,
            "assets": assets,
            "overlay_geometry_pt": overlay_geometry(asset_dir, subject),
        })
    return {
        "schema_version": 1, "exam": EXAM, "template_pack_id": PACK_ID,
        "repository": REPOSITORY,
        "github_template_folder": TREE_ROOT + quote(PACK_ROOT.relative_to(ROOT).as_posix(), safe="/"),
        "asset_policy": "Formal output must use the verified component PDF bytes as immutable background layers; "
                        "never OCR, retype, reflow, rasterize, or visually imitate their locked content. "
                        "blank-template is a review packet, not a fixed-page exam skeleton.",
        "page_size_note": "115 會考 booklets print on 595.28 x 822.05 pt; these templates print on A4 with the official "
                          "top/side positions and the page number's official distance from the bottom edge.",
        "installation_contract": {"required_subject_count": len(subjects), "required_download_url_count": total,
                                  "store_all_download_url_records": True,
                                  "download_pdf_binaries_during_installation": False,
                                  "download_timing": "after installation, when generation starts for the requested subject"},
        "formal_composition": {
            "exact_binary_base_required": True, "template_retypesetting_allowed": False,
            "template_rasterization_allowed": False, "runtime_fetch_scope": "requested_subject_production_components_only",
            "allowed_overlays": ["academic_year", "exam_name", "cover_page_count", "cover_item_count", "page_number",
                                 "newly_authored_body_within_the_inner_body_box"],
            "turn_cue_rule": "Even inner pages before the last question page use inner-even-turn-blank "
                             "(「請翻頁繼續作答」, as 115 prints it); solution booklets never print the cue.",
        },
        "dynamic_fields": ["academic_year", "exam_name", "cover_page_count", "cover_item_count", "page_number"],
        "locked_fields": ["subject_title", "duration", "clock_times", "answer_mode_instructions",
                          "answer_sheet_kind", "math_formula_sheet"],
        "asset_count": total,
        "subjects": subjects,
    }


def write_pack_manifest() -> None:
    manifest = {
        "template_pack_id": PACK_ID, "template_kind": "layout-only", "exam": EXAM, "reference_academic_year": 115,
        "curriculum": "108", "canonical_renderer": "scripts/render_cap_template_assets.py",
        "branding_policy": "保留115會考題本的封面階層與作答說明，生成卷固定標示 Taiwan Exam 模擬試題，不冒充國中教育會考正式試題。",
        "pagination_policy": "正文先依實際內容分頁，再填入頁碼、封面頁數與題數；不得用固定頁數空殼逼迫正文縮放。",
        "subjects": {s: {"template_key": template_key(s), "slug": c["slug"], "asset_dir": f'assets/{c["slug"]}',
                         "official_items": c["items"], "official_inner_pages": c["pages"], "duration_minutes": c["duration"]}
                     for s, c in SUBJECTS.items()},
    }
    (PACK_ROOT / "template-pack.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="產生115會考版型資產（不產生題目）")
    parser.add_argument("--build-all", action="store_true", help="重建六科模板PDF與模板對照表")
    parser.add_argument("--map-only", action="store_true", help="只依現有PDF重寫模板對照表")
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--kai-font", type=Path, help="TW-Kai-98_1.ttf (the preflight's pinned 楷體)")
    parser.add_argument("--sung-font", type=Path, help="TW-Sung-98_1.ttf (the preflight's pinned 明體)")
    args = parser.parse_args(argv)
    try:
        if args.build_all:
            browser = find_browser(args.browser)
            fonts = {k: v for k, v in (("kai", args.kai_font), ("sung", args.sung_font)) if v}
            for subject in SUBJECT_ORDER:
                build_subject(browser, subject, PACK_ROOT / "assets", fonts)
        elif not args.map_only:
            raise ValueError("請指定 --build-all 或 --map-only")
        write_pack_manifest()
        mapping = build_map()
        MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"map": str(MAP_PATH), "subjects": len(mapping["subjects"]),
                          "asset_count": mapping["asset_count"]}, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - command-line boundary
        print(f"錯誤：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
