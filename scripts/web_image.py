#!/usr/bin/env python3
"""Find and use NEW real photographs from Wikimedia Commons, with full provenance.

  search  "嘉南大圳" [--limit 8]                     candidates: size, license, creator, preview
  use     --title "File:…jpg" --run-dir RUN --output figures/q12.jpg [--crop x0,y0,x1,y1] [--kind photo]
          → visual_asset and visual_spec for the item (generation_mode web_source)

Every 會考 photograph must be newly found when the preflight finds the web reachable;
scripts/photo_library.py (59 bundled photos, reused by every paper) is only the offline fallback. Search
in Chinese and English; prefer documentary photos, maps and archival images whose content
carries answer evidence. Never print the credit in the booklet: the record is the attribution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "taiwan-cap-exam/1.0 (https://github.com/alenhu2005/taiwan-cap-exam)"
MANIFEST = Path(__file__).resolve().parents[1] / "references" / "photo-library-manifest.json"
RASTER = {"image/jpeg", "image/png", "image/tiff", "image/webp"}


def _get(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _text(value) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", str(value or "")))).strip()


def library_pages() -> set[str]:
    """Commons pages already in the bundled photo library (reused by every paper)."""
    try:
        items = json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]
    except (OSError, KeyError, ValueError):
        return set()
    return {urllib.parse.unquote(i["source"]["page"]).replace(" ", "_") for i in items if i.get("source", {}).get("page")}


def candidates(payload: dict) -> list[dict]:
    """Rows from a Commons generator=search query with imageinfo/extmetadata."""
    library = library_pages()
    rows = []
    for page in (payload.get("query") or {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        if info.get("mime") not in RASTER:
            continue
        url = info.get("descriptionurl") or ""
        rows.append({
            "title": page.get("title"), "page": url, "width": info.get("width"), "height": info.get("height"),
            "license": _text((meta.get("LicenseShortName") or {}).get("value")),
            "creator": _text((meta.get("Artist") or {}).get("value"))[:120],
            "date": re.split(r"date QS|QS:", _text((meta.get("DateTimeOriginal") or {}).get("value")))[0].strip()[:40],
            "description": _text((meta.get("ImageDescription") or {}).get("value"))[:200],
            "preview": info.get("thumburl") or info.get("url"),
            "in_bundled_library": urllib.parse.unquote(url).replace(" ", "_") in library,
        })
    rows.sort(key=lambda r: (r["in_bundled_library"], -(r["width"] or 0)))
    return rows


def search(query: str, limit: int = 8, offset: int = 0) -> list[dict]:
    params = {"action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": query, "gsrlimit": limit,
              "gsroffset": offset,
              "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600, "format": "json"}
    return candidates(json.loads(_get(API + "?" + urllib.parse.urlencode(params))))


def use(title: str, run_dir: Path, output: str, crop: str | None = None, kind: str = "photo",
        print_width_cm: float = 12.0) -> dict:
    import pymupdf
    params = {"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
              "iiurlwidth": 1600, "format": "json"}
    rows = candidates(json.loads(_get(API + "?" + urllib.parse.urlencode(params))))
    if not rows:
        raise SystemExit(f"{title}: not a raster image on Wikimedia Commons")
    row = rows[0]
    run_dir = Path(run_dir).resolve()
    data = _get(row["preview"], timeout=60)
    digest = hashlib.sha256(data).hexdigest()
    store = run_dir / "web-images"
    store.mkdir(parents=True, exist_ok=True)
    source = store / f"{digest[:16]}{Path(urllib.parse.urlparse(row['preview']).path).suffix.lower() or '.jpg'}"
    source.write_bytes(data)
    pix = pymupdf.Pixmap(data)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    box = [0.0, 0.0, 1.0, 1.0] if not crop else [float(v) for v in crop.split(",")]
    if len(box) != 4 or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
        raise SystemExit("--crop takes x0,y0,x1,y1 as fractions of the width and height")
    x0, y0, x1, y1 = (round(box[0] * pix.width), round(box[1] * pix.height), round(box[2] * pix.width), round(box[3] * pix.height))
    doc = pymupdf.open()
    page = doc.new_page(width=x1 - x0, height=y1 - y0)
    page.insert_image(pymupdf.Rect(-x0, -y0, pix.width - x0, pix.height - y0), pixmap=pix)
    gray = page.get_pixmap(dpi=72, colorspace=pymupdf.csGRAY, clip=page.rect)
    target = (run_dir / output).resolve()
    if not target.is_relative_to(run_dir):
        raise SystemExit("--output must be inside the run directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gray.tobytes("jpg", jpg_quality=85))
    relative = lambda p: Path(os.path.relpath(p, run_dir)).as_posix()
    dpi = int(gray.width / (print_width_cm / 2.54))
    public = re.search(r"public domain|cc0|pd", row["license"], re.I)
    used = store / "used.json"
    log = json.loads(used.read_text(encoding="utf-8")) if used.is_file() else []
    log.append({"title": row["title"], "page": row["page"], "output": relative(target)})
    used.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "visual_asset": {"path": relative(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "grayscale": True},
        "visual_spec": {
            "kind": kind, "generation_mode": "web_source",
            "source_rights": "public_domain" if public else "web_sourced",
            "source_url": row["page"], "source_creator": row["creator"] or "unknown", "source_site": "Wikimedia Commons",
            "source_retrieved_at": dt.date.today().isoformat(), "source_published_at": row["date"] or None,
            "license_or_authorization": row["license"] or "see source page",
            "source_asset_path": relative(source), "source_asset_sha256": digest,
            "crop_description": "full frame" if not crop else f"crop x {box[0]:g}-{box[2]:g}, y {box[1]:g}-{box[3]:g}",
            "processing_steps": ["downloaded 1600 px rendition", *(["cropped"] if crop else []), "grayscale", "JPEG quality 85"],
            "tonal_transform": "grayscale", "min_raster_dpi": dpi,
        },
        "notes": [f"Printed {print_width_cm:g} cm wide it gives {dpi} dpi" + ("" if dpi >= 200 else "; print it narrower"),
                  *(["This image is also in the bundled photo library; a fresher one avoids repeating other papers."]
                    if row["in_bundled_library"] else []),
                  "Fill answer_bearing_features, role, grayscale_review and validation_checks after looking at it.",
                  "Do not print the credit in the booklet; the record above is the attribution."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--limit", type=int, default=8)
    s.add_argument("--offset", type=int, default=0, help="skip the first N results (vary between papers)")
    u = sub.add_parser("use"); u.add_argument("--title", required=True); u.add_argument("--run-dir", type=Path, required=True)
    u.add_argument("--output", required=True); u.add_argument("--crop"); u.add_argument("--kind", default="photo")
    u.add_argument("--print-width-cm", type=float, default=12.0)
    args = parser.parse_args()
    try:
        result = (search(args.query, args.limit, args.offset) if args.command == "search" else
                  use(args.title, args.run_dir, args.output, args.crop, args.kind, args.print_width_cm))
    except OSError as exc:
        print(json.dumps({"status": "unreachable", "error": str(exc),
                          "fallback": "python scripts/photo_library.py fetch --run-dir RUN"}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
