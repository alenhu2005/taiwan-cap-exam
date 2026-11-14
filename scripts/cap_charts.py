#!/usr/bin/env python3
"""Ready-made 會考 charts and maps as one-page vector PDFs (with a PNG preview beside each).

A 54-item 會考社會 run wrote 15 drawing scripts of its own (bar and line charts, a population
pyramid, a climate graph, a county map from a downloaded TopoJSON) and saved a 35 MB figure.
These presets take a small JSON spec, print in the booklet's faces (Times numerals, the run's
明體 for Chinese), stay readable in grayscale (fills are gray levels or hatching, lines differ by
dash and marker) and embed only the glyphs they use.

  python scripts/cap_draw.py render spec.json fig.pdf --font RUN/fonts/TW-Sung-98_1.ttf

Specs ("chart" picks the preset; sizes in pt; every label is the student's evidence, never the answer):
  {"chart": "bar", "width_pt": 260, "height_pt": 170, "categories": ["甲", "乙"], "unit": "萬人",
   "series": [{"name": "2015", "values": [3, 5]}, {"name": "2025", "values": [4, 6]}], "panels": false}
  {"chart": "line", "categories": ["2019", "2020"], "series": [{"name": "甲", "values": [1, 2]}], "unit": "%"}
  {"chart": "climate", "place": "某地", "temperature": [12 values ℃], "rainfall": [12 values mm]}
  {"chart": "pyramid", "groups": ["0-4", "5-9", …], "male": [%…], "female": [%…], "unit": "%"}
  {"chart": "profile", "points": [[0, 20], [5, 350], …], "labels": [{"at": 5, "text": "甲"}], "unit_x": "公里", "unit_y": "公尺"}
  {"chart": "table", "header": ["項目", "甲", "乙"], "rows": [["人口", "3", "5"]]}
  {"chart": "map", "region": "taiwan" | "east-asia" | "world", "fills": {"臺北市": 1, "高雄市": 3},
   "legend": ["低", "中", "高"], "points": [{"lon": 121.5, "lat": 25.0, "label": "甲"}], "insets": true}
  {"chart": "card", "title": "史料一", "lines": ["…原文…"], "source": "改寫自 …"}
Map fills are classes 1-4 (four gray levels, light to dark, readable in grayscale); base maps come from
exam_packs/會考/maps (內政部國土測繪中心 縣市界線, Natural Earth), simplified for illustration.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pymupdf

MAPS = Path(__file__).resolve().parents[1] / "exam_packs" / "會考" / "maps"
GRAYS = {1: 0.88, 2: 0.70, 3: 0.48, 4: 0.30}
SERIES_FILLS = (0.25, 0.65, 0.9, 0.45)
DASHES = (None, "[4 2] 0", "[1 2] 0", "[6 2 1 2] 0")
LABEL, NUMBER = 9.5, 8.5


class Canvas:
    def __init__(self, width: float, height: float, font: Path | None = None):
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=width, height=height)
        self.w, self.h = width, height
        self.fonts = {"roman": pymupdf.Font("tiro"), "italic": pymupdf.Font("tiit"),
                      "cjk": pymupdf.Font(fontfile=str(font)) if font else pymupdf.Font("cjk")}

    def runs(self, text):
        for match in re.finditer(r"[A-Za-z0-9.,%°℃′−+\-()/:~～ ]+|[^A-Za-z0-9.,%°℃′−+\-()/:~～ ]+", str(text)):
            chunk = match.group(0)
            face = "roman" if all(self.fonts["roman"].has_glyph(ord(c)) for c in chunk) else "cjk"
            yield chunk, face

    def width(self, text, size=LABEL):
        return sum(self.fonts[f].text_length(t, fontsize=size) for t, f in self.runs(text))

    def text(self, text, x, y, size=LABEL, anchor="left", color=(0, 0, 0)):
        if anchor != "left":
            x -= self.width(text, size) / (2 if anchor == "center" else 1)
        for chunk, face in self.runs(text):
            writer = pymupdf.TextWriter(self.page.rect)
            writer.append((x, y), chunk, font=self.fonts[face], fontsize=size)
            writer.write_text(self.page, color=color)
            x += self.fonts[face].text_length(chunk, fontsize=size)

    def line(self, a, b, width=0.8, dash=None, gray=0.0):
        shape = self.page.new_shape()
        shape.draw_line(a, b)
        shape.finish(color=(gray,) * 3, width=width, dashes=dash)
        shape.commit()

    def rect(self, r, fill=None, width=0.6, hatch=False):
        shape = self.page.new_shape()
        shape.draw_rect(pymupdf.Rect(r))
        shape.finish(color=(0, 0, 0), fill=(fill,) * 3 if fill is not None else None, width=width)
        shape.commit()
        if hatch:
            self.hatch_rect(pymupdf.Rect(r))

    def hatch_rect(self, r, step=3.0):
        shape = self.page.new_shape()
        k = -r.height
        while k < r.width:
            a = pymupdf.Point(r.x0 + max(k, 0), r.y1 - max(0, -k))
            b = pymupdf.Point(r.x0 + min(k + r.height, r.width), r.y1 - min(r.height, r.width - k))
            shape.draw_line(a, b)
            k += step
        shape.finish(color=(0, 0, 0), width=0.35)
        shape.commit()

    def polygon(self, points, fill=None, width=0.5, close=True):
        shape = self.page.new_shape()
        shape.draw_polyline(points + ([points[0]] if close else []))
        shape.finish(color=(0, 0, 0), fill=(fill,) * 3 if fill is not None else None, width=width, closePath=close)
        shape.commit()

    def save(self, output: Path) -> dict:
        self.doc.subset_fonts()
        self.doc.save(output, garbage=4, deflate=True)
        preview = Path(output).with_suffix(".png")
        self.page.get_pixmap(dpi=150, alpha=False).save(preview)
        self.doc.close()
        return {"path": str(output), "preview": str(preview), "width_pt": round(self.w, 1), "height_pt": round(self.h, 1)}


def nice_max(value: float) -> tuple[float, float]:
    """(axis maximum, tick step) with 4-6 ticks."""
    if value <= 0:
        return 1, 0.2
    raw = value / 5
    power = 10 ** math.floor(math.log10(raw))
    step = min((s * power for s in (1, 2, 2.5, 5, 10) if s * power >= raw), default=power * 10)
    return math.ceil(value / step) * step, step


def axes(c: Canvas, box, ymax, step, unit, categories, right=None):
    x0, y0, x1, y1 = box
    c.line((x0, y1), (x1, y1)); c.line((x0, y0), (x0, y1))
    v = 0.0
    while v <= ymax + 1e-9:
        y = y1 - (y1 - y0) * v / ymax
        c.line((x0 - 3, y), (x0, y))
        c.line((x0, y), (x1, y), width=0.3, gray=0.75)
        c.text(f"{v:g}", x0 - 5, y + 3, NUMBER, "right")
        v += step
    if unit:
        c.text(f"（{unit}）", x0 - 4, y0 - 7, NUMBER, "center")
    slot = (x1 - x0) / max(1, len(categories))
    for i, name in enumerate(categories):
        c.text(name, x0 + slot * (i + 0.5), y1 + 12, NUMBER, "center")
    return slot


def legend(c: Canvas, names, x, y, kind="fill"):
    if x is None:   # right-aligned along the top edge, clear of the unit label at the left
        x = c.w - 8 - sum(22 + c.width(n, NUMBER) + 8 for n in names) + 8
    for i, name in enumerate(names):
        if kind == "fill":
            c.rect((x, y - 7, x + 10, y), fill=SERIES_FILLS[i % 4])
        else:
            c.line((x, y - 3), (x + 14, y - 3), width=1.0, dash=DASHES[i % 4])
        c.text(name, x + 16, y, NUMBER)
        x += 22 + c.width(name, NUMBER) + 8


def bar(spec, c: Canvas):
    series = spec["series"]
    categories = spec["categories"]
    top = max(max(s["values"]) for s in series)
    ymax, step = nice_max(spec.get("ymax") or top)
    panels = spec.get("panels") and len(series) > 1
    groups = [[s] for s in series] if panels else [series]
    width = (c.w - 50) / len(groups)
    for g, group in enumerate(groups):
        box = (40 + g * width, 28, 40 + (g + 1) * width - 12, c.h - 24)
        slot = axes(c, box, ymax, step, spec.get("unit") if g == 0 else None, categories)
        bar_w = slot * 0.7 / len(group)
        for k, s in enumerate(group):
            for i, value in enumerate(s["values"]):
                x = box[0] + slot * i + slot * 0.15 + bar_w * k
                y = box[3] - (box[3] - box[1]) * value / ymax
                c.rect((x, y, x + bar_w, box[3]), fill=SERIES_FILLS[(g if panels else k) % 4])
                if spec.get("value_labels"):
                    c.text(f"{value:g}", x + bar_w / 2, y - 2, NUMBER - 1, "center")
        if panels:
            c.text(group[0]["name"], (box[0] + box[2]) / 2, 14, LABEL, "center")
    if not panels and len(series) > 1:
        legend(c, [s["name"] for s in series], None, 14)


def line_chart(spec, c: Canvas):
    series, categories = spec["series"], spec["categories"]
    lo = min(min(s["values"]) for s in series)
    top = max(max(s["values"]) for s in series)
    ymax, step = nice_max(spec.get("ymax") or top)
    box = (40, 28, c.w - 12, c.h - 24)
    slot = axes(c, box, ymax, step, spec.get("unit"), categories)
    markers = ("circle", "square", "triangle", "cross")
    for k, s in enumerate(series):
        pts = [pymupdf.Point(box[0] + slot * (i + 0.5), box[3] - (box[3] - box[1]) * v / ymax) for i, v in enumerate(s["values"])]
        shape = c.page.new_shape(); shape.draw_polyline(pts)
        shape.finish(color=(0, 0, 0), width=1.0, dashes=DASHES[k % 4], closePath=False); shape.commit()
        for p in pts:
            m = markers[k % 4]
            shape = c.page.new_shape()
            if m == "circle":
                shape.draw_circle(p, 2.0)
            elif m == "square":
                shape.draw_rect(pymupdf.Rect(p.x - 2, p.y - 2, p.x + 2, p.y + 2))
            elif m == "triangle":
                shape.draw_polyline([p + (0, -2.6), p + (2.4, 1.8), p + (-2.4, 1.8), p + (0, -2.6)])
            else:
                shape.draw_line(p + (-2, -2), p + (2, 2)); shape.draw_line(p + (-2, 2), p + (2, -2))
            shape.finish(color=(0, 0, 0), fill=(0, 0, 0) if m != "cross" else None, width=0.8); shape.commit()
    if len(series) > 1:
        legend(c, [s["name"] for s in series], None, 14, kind="line")
    del lo


def climate(spec, c: Canvas):
    temps, rain = spec["temperature"], spec["rainfall"]
    box = (40, 30, c.w - 40, c.h - 24)
    rmax, rstep = nice_max(max(rain))
    tmin = min(0, math.floor(min(temps) / 10) * 10)
    tmax = math.ceil(max(temps) / 10) * 10
    slot = (box[2] - box[0]) / 12
    c.line((box[0], box[3]), (box[2], box[3])); c.line((box[0], box[1]), (box[0], box[3])); c.line((box[2], box[1]), (box[2], box[3]))
    for i in range(6):
        v = tmin + (tmax - tmin) * i / 5
        y = box[3] - (box[3] - box[1]) * i / 5
        c.text(f"{v:g}", box[0] - 4, y + 3, NUMBER, "right")
        c.text(f"{rmax * i / 5:g}", box[2] + 4, y + 3, NUMBER)
        c.line((box[0], y), (box[2], y), width=0.3, gray=0.8)
    c.text("（℃）", box[0] - 4, box[1] - 8, NUMBER, "center"); c.text("（mm）", box[2] + 6, box[1] - 8, NUMBER, "center")
    for i, value in enumerate(rain):
        x = box[0] + slot * i + slot * 0.2
        c.rect((x, box[3] - (box[3] - box[1]) * value / rmax, x + slot * 0.6, box[3]), fill=0.72)
        c.text(str(i + 1), box[0] + slot * (i + 0.5), box[3] + 11, NUMBER, "center")
    pts = [pymupdf.Point(box[0] + slot * (i + 0.5), box[3] - (box[3] - box[1]) * (t - tmin) / (tmax - tmin)) for i, t in enumerate(temps)]
    shape = c.page.new_shape(); shape.draw_polyline(pts); shape.finish(color=(0, 0, 0), width=1.2, closePath=False); shape.commit()
    for p in pts:
        shape = c.page.new_shape(); shape.draw_circle(p, 1.8); shape.finish(color=(0, 0, 0), fill=(0, 0, 0)); shape.commit()
    c.text("（月）", box[2] - 4, box[3] + 21, NUMBER, "right")
    if spec.get("place"):
        c.text(spec["place"], (box[0] + box[2]) / 2, 14, LABEL, "center")


def pyramid(spec, c: Canvas):
    groups, male, female = spec["groups"], spec["male"], spec["female"]
    top, step = nice_max(max(max(male), max(female)))
    mid = c.w / 2
    half = (c.w - 70) / 2
    row = (c.h - 44) / len(groups)
    for i, name in enumerate(groups):
        y = c.h - 26 - row * (i + 1)
        c.rect((mid - 14 - half * male[i] / top, y + 1, mid - 14, y + row - 1), fill=0.35)
        c.rect((mid + 14, y + 1, mid + 14 + half * female[i] / top, y + row - 1), fill=0.8)
        c.text(name, mid, y + row / 2 + 3, NUMBER - 1, "center")
    base = c.h - 26
    c.line((mid - 14 - half, base), (mid - 14, base)); c.line((mid + 14, base), (mid + 14 + half, base))
    v = 0.0
    while v <= top + 1e-9:
        for sign, origin in ((-1, mid - 14), (1, mid + 14)):
            x = origin + sign * half * v / top
            c.line((x, base), (x, base + 3))
            c.text(f"{v:g}", x, base + 12, NUMBER - 1, "center")
        v += step
    c.text("男", mid - 14 - half / 2, 14, LABEL, "center"); c.text("女", mid + 14 + half / 2, 14, LABEL, "center")
    if spec.get("unit"):
        c.text(f"（{spec['unit']}）", c.w - 6, base + 22, NUMBER, "right")


def profile(spec, c: Canvas):
    pts = spec["points"]
    xmax = max(p[0] for p in pts)
    ymax, step = nice_max(max(p[1] for p in pts))
    box = (44, 24, c.w - 14, c.h - 26)
    sx = lambda x: box[0] + (box[2] - box[0]) * x / xmax
    sy = lambda y: box[3] - (box[3] - box[1]) * y / ymax
    shape = c.page.new_shape()
    shape.draw_polyline([pymupdf.Point(sx(pts[0][0]), box[3])] + [pymupdf.Point(sx(x), sy(y)) for x, y in pts] +
                        [pymupdf.Point(sx(pts[-1][0]), box[3])])
    shape.finish(color=(0, 0, 0), fill=(0.8,) * 3, width=1.0, closePath=True); shape.commit()
    c.line((box[0], box[3]), (box[2], box[3])); c.line((box[0], box[1]), (box[0], box[3]))
    v = 0.0
    while v <= ymax + 1e-9:
        c.text(f"{v:g}", box[0] - 4, sy(v) + 3, NUMBER, "right"); c.line((box[0] - 3, sy(v)), (box[0], sy(v)))
        v += step
    xs, xstep = nice_max(xmax)
    v = 0.0
    while v <= xmax + 1e-9:
        c.text(f"{v:g}", sx(v), box[3] + 11, NUMBER, "center")
        v += xstep
    c.text(f"（{spec.get('unit_y', '公尺')}）", box[0] - 6, box[1] - 8, NUMBER, "center")
    c.text(f"（{spec.get('unit_x', '公里')}）", box[2], box[3] + 22, NUMBER, "right")
    for label in spec.get("labels") or []:
        y = next((py for px, py in pts if px >= label["at"]), pts[-1][1])
        c.text(label["text"], sx(label["at"]), sy(y) - 6, LABEL, "center")


def table(spec, c: Canvas):
    rows = [spec["header"]] + spec["rows"]
    cols = len(spec["header"])
    widths = [max(c.width(str(r[k]), LABEL) for r in rows) + 14 for k in range(cols)]
    scale = min(1.0, (c.w - 4) / sum(widths))
    widths = [w * scale for w in widths]
    height = 18
    x0 = (c.w - sum(widths)) / 2
    for i, row in enumerate(rows):
        x = x0
        for k, cell in enumerate(row):
            c.rect((x, 2 + i * height, x + widths[k], 2 + (i + 1) * height), fill=0.9 if i == 0 else None, width=0.6)
            c.text(str(cell), x + widths[k] / 2, 2 + i * height + 12.5, LABEL, "center")
            x += widths[k]


def card(spec, c: Canvas):
    c.rect((2, 2, c.w - 2, c.h - 2), width=0.8)
    y = 18
    if spec.get("title"):
        c.text(spec["title"], 12, y, LABEL + 0.5); y += 16
    for line in spec.get("lines") or []:
        c.text(line, 14, y, LABEL); y += 15
    if spec.get("source"):
        c.text(spec["source"], c.w - 10, c.h - 9, NUMBER, "right")


def project(lon, lat, view):
    """Equirectangular with cos(mid-latitude) scaling into view = (lon0, lat0, lon1, lat1, box)."""
    lon0, lat0, lon1, lat1, (x0, y0, x1, y1) = view
    k = math.cos(math.radians((lat0 + lat1) / 2))
    sx = (x1 - x0) / ((lon1 - lon0) * k)
    sy = (y1 - y0) / (lat1 - lat0)
    s = min(sx, sy)
    return pymupdf.Point(x0 + (lon - lon0) * k * s, y1 - (lat - lat0) * s)


def draw_regions(c: Canvas, regions, view, fills, clip=None, width=0.4):
    for region in regions:
        cls = fills.get(region["name"]) or fills.get(region.get("name_en") or "") or fills.get(region.get("code") or "")
        for ring in region["rings"]:
            if clip and not any(clip[0] <= x <= clip[2] and clip[1] <= y <= clip[3] for x, y in ring):
                continue
            pts = [project(x, y, view) for x, y in ring]
            c.polygon(pts, fill=GRAYS.get(cls) if cls else 1.0, width=width)


def map_chart(spec, c: Canvas):
    region = spec.get("region", "taiwan")
    fills = spec.get("fills") or {}
    if region == "taiwan":
        data = json.loads((MAPS / "taiwan-counties.json").read_text(encoding="utf-8"))["counties"]
        main = [r for r in data if r["name"] not in ("金門縣", "連江縣")]
        insets = spec.get("insets", True)
        view = (119.3, 21.85, 122.1, 25.35, (74 if insets else 10, 8, c.w - 10, c.h - 10))
        draw_regions(c, main, view, fills)
        if insets:
            # 金門 and 馬祖 sit outside the main frame, as school maps print them; their islands are small,
            # so the frames are generous and the outlines heavier.
            frames = (("金門縣", (118.12, 24.36, 118.52, 24.56), (6, 8, 70, 50)),
                      ("連江縣", (119.88, 25.93, 120.53, 26.40), (6, 64, 70, 128)))
            for name, box, frame in frames:
                c.rect(frame, width=0.5)
                draw_regions(c, [r for r in data if r["name"] == name],
                             (*box, (frame[0] + 3, frame[1] + 3, frame[2] - 3, frame[3] - 3)), fills, width=0.7)
                c.text(name[:2], frame[0] + 2, frame[3] + 10, NUMBER - 1)
    else:
        data = json.loads((MAPS / f"{region}-countries.json").read_text(encoding="utf-8"))["countries"]
        extent = spec.get("extent") or ((95, 0, 150, 50) if region == "east-asia" else (-170, -58, 180, 80))
        view = (*extent, (8, 8, c.w - 8, c.h - 8))
        draw_regions(c, data, view, fills, clip=extent)
    for point in spec.get("points") or []:
        p = project(point["lon"], point["lat"], view)
        shape = c.page.new_shape(); shape.draw_circle(p, 2.2); shape.finish(color=(0, 0, 0), fill=(0, 0, 0)); shape.commit()
        if point.get("label"):
            c.text(point["label"], p.x + 4, p.y - 3, LABEL)
    if spec.get("compass", True):
        x, y = c.w - 20, 22
        c.polygon([pymupdf.Point(x, y - 12), pymupdf.Point(x + 4, y), pymupdf.Point(x - 4, y)], fill=0.0)
        c.text("N", x, y - 15, NUMBER, "center")
    names = spec.get("legend") or []
    left = 8 if region == "taiwan" else c.w - 70   # Taiwan: over the Strait, clear of the island
    for i, name in enumerate(names):
        y = c.h - 12 - (len(names) - 1 - i) * 13
        c.rect((left, y - 8, left + 10, y), fill=GRAYS[min(4, i + 1)])
        c.text(name, left + 14, y, NUMBER)


PRESETS = {"bar": bar, "line": line_chart, "climate": climate, "pyramid": pyramid, "profile": profile,
           "table": table, "card": card, "map": map_chart}
DEFAULT_SIZE = {"map": (230, 280), "card": (300, 120), "table": (300, 80), "pyramid": (240, 200)}


def render(spec: dict, output: Path, font: Path | None = None) -> dict:
    chart = spec["chart"]
    if chart not in PRESETS:
        raise ValueError(f"chart must be one of {', '.join(PRESETS)}")
    width, height = DEFAULT_SIZE.get(chart, (260, 170))
    c = Canvas(spec.get("width_pt", width), spec.get("height_pt", height), font)
    PRESETS[chart](spec, c)
    return c.save(output)
