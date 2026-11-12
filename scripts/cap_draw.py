#!/usr/bin/env python3
"""Vector figures for 會考 items: one-page PDFs with embedded fonts, drawn from a small JSON spec.

A math author (M1111, 2026-11) wrote a drawing library of their own and lost time to it: the SVG
renderer's Times had no 「−」「…」「′」, white boxes behind labels showed as frames on the grid, and
labels sat on lines. This draws what 會考 figures use, in the booklet's faces (Times italic point
names, Times numerals, the run's 明體 for Chinese), and keeps labels off lines with a thin outline
halo instead of a box.

  python scripts/cap_draw.py render spec.json fig.pdf [--font RUN/fonts/TW-Sung-98_1.ttf]
  python scripts/cap_draw.py options spec.json --out-dir figs/ [--font …]   four option figures, one frame

Spec (units are the figure's own coordinates, y upward; sizes in pt):
  {"width_pt": 220, "view": [xmin, xmax, ymin, ymax],
   "items": [
     {"grid": {"step": 1}},                                   light grid lines
     {"axes": {"ticks": 2, "labels": true, "names": ["x", "y"]}},
     {"segment": [[0, 0], [8, 6]], "dash": false, "width": 0.9},
     {"polygon": [[0, 0], [8, 6], [14, -2]], "fill": 0.9},     fill gray level, omit for none
     {"circle": [[0, 0], 5]}, {"arc": [[0, 0], 5, 30, 120]},  degrees, counter-clockwise
     {"point": [8, 6], "label": "A", "at": "auto"},           at: auto|n|ne|e|se|s|sw|w|nw
     {"angle": [[1, 0], [0, 0], [0, 1]], "label": "40°"},     arc at the middle vertex
     {"right_angle": [[1, 0], [0, 0], [0, 1]]},
     {"ticks": [[0, 0], [8, 6]], "count": 1},                 equal-length marks
     {"text": "圖書館", "at": [8, 7], "size": 9}               Chinese or mixed text
   ]}
The labels a student reads are the figure's evidence: never print the answer on it.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import pymupdf

LABEL_PT, NUMBER_PT, TEXT_PT = 11.0, 9.0, 9.5
DIRECTIONS = {"n": (0, 1), "ne": (.7, .7), "e": (1, 0), "se": (.7, -.7), "s": (0, -1), "sw": (-.7, -.7),
              "w": (-1, 0), "nw": (-.7, .7)}


class Figure:
    def __init__(self, width_pt: float, view, *, font: Path | None = None, margin: float = 14):
        self.xmin, self.xmax, self.ymin, self.ymax = view
        self.margin = margin
        self.scale = (width_pt - 2 * margin) / (self.xmax - self.xmin)
        self.height = (self.ymax - self.ymin) * self.scale + 2 * margin
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=width_pt, height=self.height)
        self.fonts = {"italic": pymupdf.Font("tiit"), "roman": pymupdf.Font("tiro"),
                      "cjk": pymupdf.Font(fontfile=str(font)) if font else pymupdf.Font("cjk")}
        self.has_grid = False
        self.lines: list[tuple] = []   # page-space segments, for keeping labels off them

    def xy(self, p) -> pymupdf.Point:
        return pymupdf.Point(self.margin + (p[0] - self.xmin) * self.scale,
                             self.height - self.margin - (p[1] - self.ymin) * self.scale)

    # -- strokes --------------------------------------------------------------------------------
    def _stroke(self, shape, width=0.9, dash=False, fill=None, gray=0.0):
        shape.finish(color=(gray,) * 3, width=width, dashes="[3 2] 0" if dash else None,
                     fill=(fill,) * 3 if fill is not None else None, closePath=False)
        shape.commit()

    def segment(self, a, b, *, dash=False, width=0.9):
        shape = self.page.new_shape()
        shape.draw_line(self.xy(a), self.xy(b))
        self._stroke(shape, width, dash)
        self.lines.append((self.xy(a), self.xy(b)))

    def polygon(self, points, *, fill=None, dash=False, width=0.9):
        shape = self.page.new_shape()
        shape.draw_polyline([self.xy(p) for p in points] + [self.xy(points[0])])
        self._stroke(shape, width, dash, fill)
        for a, b in zip(points, points[1:] + points[:1]):
            self.lines.append((self.xy(a), self.xy(b)))

    def circle(self, center, r, *, dash=False, width=0.9):
        shape = self.page.new_shape()
        shape.draw_circle(self.xy(center), r * self.scale)
        self._stroke(shape, width, dash)
        c = self.xy(center)
        for k in range(36):   # coarse chords so labels avoid the curve
            a, b = math.radians(k * 10), math.radians(k * 10 + 10)
            self.lines.append((c + (r * self.scale * math.cos(a), -r * self.scale * math.sin(a)),
                               c + (r * self.scale * math.cos(b), -r * self.scale * math.sin(b))))

    def arc(self, center, r, start, end, *, width=0.9, dash=False):
        c, steps = self.xy(center), max(8, int(abs(end - start) / 4))
        pts = [c + (r * self.scale * math.cos(math.radians(start + (end - start) * k / steps)),
                    -r * self.scale * math.sin(math.radians(start + (end - start) * k / steps))) for k in range(steps + 1)]
        shape = self.page.new_shape()
        shape.draw_polyline(pts)
        self._stroke(shape, width, dash)
        self.lines += list(zip(pts, pts[1:]))

    def grid(self, step=1, gray=0.75):
        self.has_grid = True
        shape = self.page.new_shape()
        x = math.ceil(self.xmin / step) * step
        while x <= self.xmax + 1e-9:
            shape.draw_line(self.xy((x, self.ymin)), self.xy((x, self.ymax)))
            x += step
        y = math.ceil(self.ymin / step) * step
        while y <= self.ymax + 1e-9:
            shape.draw_line(self.xy((self.xmin, y)), self.xy((self.xmax, y)))
            y += step
        self._stroke(shape, 0.4, gray=gray)

    def axes(self, ticks=None, labels=True, names=("x", "y")):
        shape = self.page.new_shape()
        for a, b in (((self.xmin, 0), (self.xmax, 0)), ((0, self.ymin), (0, self.ymax))):
            shape.draw_line(self.xy(a), self.xy(b))
        self._stroke(shape, 0.9)
        self.lines += [(self.xy((self.xmin, 0)), self.xy((self.xmax, 0))), (self.xy((0, self.ymin)), self.xy((0, self.ymax)))]
        for tip, d in ((self.xy((self.xmax, 0)), (-1, 0)), (self.xy((0, self.ymax)), (0, 1))):
            shape = self.page.new_shape()
            back = pymupdf.Point(tip.x + 6 * d[0], tip.y + 6 * d[1])
            side = (3 * d[1], 3 * d[0])
            shape.draw_polyline([back + side, tip, back - side])
            self._stroke(shape, 0.9)
        if names:
            self._write(names[0], self.xy((self.xmax, 0)) + (2, 12), "italic", LABEL_PT)
            self._write(names[1], self.xy((0, self.ymax)) + (7, 8), "italic", LABEL_PT)
        self._write("O", self.xy((0, 0)) + (-10, 11), "italic", LABEL_PT)
        if ticks and labels:
            for axis in (0, 1):
                low, high = (self.xmin, self.xmax) if axis == 0 else (self.ymin, self.ymax)
                v = math.ceil(low / ticks) * ticks
                while v <= high - ticks / 2:
                    if abs(v) > 1e-9:
                        text = f"{v:g}".replace("-", "−")
                        at = self.xy((v, 0)) + (-self._width(text, "roman", NUMBER_PT) / 2, 11) if axis == 0 else \
                            self.xy((0, v)) + (-self._width(text, "roman", NUMBER_PT) - 4, 3)
                        self._write(text, at, "roman", NUMBER_PT)
                    v += ticks

    # -- marks ----------------------------------------------------------------------------------
    def right_angle(self, a, o, b, size=7):
        po, pa, pb = self.xy(o), self.xy(a), self.xy(b)
        ua, ub = _unit(pa - po), _unit(pb - po)
        shape = self.page.new_shape()
        shape.draw_polyline([po + ua * size, po + ua * size + ub * size, po + ub * size])
        self._stroke(shape, 0.7)

    def angle(self, a, o, b, label=None, radius=14):
        po, pa, pb = self.xy(o), self.xy(a), self.xy(b)
        t0 = math.degrees(math.atan2(-(pa.y - po.y), pa.x - po.x))
        t1 = math.degrees(math.atan2(-(pb.y - po.y), pb.x - po.x))
        if (t1 - t0) % 360 > 180:
            t0, t1 = t1, t0
        span = (t1 - t0) % 360
        pts = [po + (radius * math.cos(math.radians(t0 + span * k / 16)), -radius * math.sin(math.radians(t0 + span * k / 16)))
               for k in range(17)]
        shape = self.page.new_shape()
        shape.draw_polyline(pts)
        self._stroke(shape, 0.7)
        if label:
            mid = math.radians(t0 + span / 2)
            at = po + ((radius + 10) * math.cos(mid), -(radius + 10) * math.sin(mid))
            self._centered(label, at, NUMBER_PT)

    def ticks(self, a, b, count=1):
        pa, pb = self.xy(a), self.xy(b)
        mid, u = (pa + pb) * 0.5, _unit(pb - pa)
        n = pymupdf.Point(-u.y, u.x)
        shape = self.page.new_shape()
        for k in range(count):
            c = mid + u * ((k - (count - 1) / 2) * 3)
            shape.draw_line(c + n * 4, c - n * 4)
        self._stroke(shape, 0.7)

    def point(self, p, label=None, at="auto", dot=True):
        c = self.xy(p)
        if dot:
            shape = self.page.new_shape()
            shape.draw_circle(c, 1.6)
            shape.finish(color=(0, 0, 0), fill=(0, 0, 0))
            shape.commit()
        if label:
            direction = DIRECTIONS.get(at) if at != "auto" else self._free_direction(c)
            w = self._mixed_width(label, LABEL_PT)
            centre = c + (direction[0] * (5 + w / 2), -direction[1] * (5 + LABEL_PT / 2))
            self._label(label, centre)

    def text(self, value, at, size=TEXT_PT):
        self._centered(value, self.xy(at), size)

    # -- text -----------------------------------------------------------------------------------
    def _free_direction(self, c):
        best, score = (0.7, 0.7), -1
        for d in DIRECTIONS.values():
            probe = c + (d[0] * 9, -d[1] * 9)
            gap = min((_distance(probe, a, b) for a, b in self.lines), default=99)
            inside = self.margin / 2 <= probe.x <= self.page.rect.width - self.margin / 2 and \
                self.margin / 2 <= probe.y <= self.height - self.margin / 2
            if inside and gap > score:
                best, score = d, gap
        return best

    def _runs(self, value):
        """(text, face) runs: Latin letters italic (point names), digits and symbols roman, CJK 明體."""
        for match in re.finditer(r"[A-Za-z]+′*|[0-9.,°′″−+=×÷()%:]+|\s+|[^\sA-Za-z0-9.,°′″−+=×÷()%:]+", value):
            chunk = match.group(0)
            face = "italic" if chunk[0].isascii() and chunk[0].isalpha() else \
                "roman" if all(self.fonts["roman"].has_glyph(ord(ch)) for ch in chunk) else "cjk"
            yield chunk, face

    def _width(self, text, face, size):
        return self.fonts[face].text_length(text, fontsize=size)

    def _mixed_width(self, value, size):
        return sum(self._width(t, f, size) for t, f in self._runs(value))

    def _write(self, value, at, face=None, size=LABEL_PT):
        runs = [(value, face)] if face else list(self._runs(value))
        x = at.x
        for text, f in runs:
            if text.strip():
                # Over a grid, a white outline under the glyphs keeps grid lines off the letters (never a
                # box, which printed as a frame). TextWriter, not insert_text: the built-in Times then
                # keeps 「−」「′」「…」 instead of encoding them as 「·」.
                for halo in ((True, False) if self.has_grid else (False,)):
                    writer = pymupdf.TextWriter(self.page.rect)
                    writer.append((x, at.y), text, font=self.fonts[f], fontsize=size)
                    writer.write_text(self.page, color=(1, 1, 1) if halo else (0, 0, 0), render_mode=1 if halo else 0)
            x += self._width(text, f, size)

    def _centered(self, value, at, size):
        self._write(value, at + (-self._mixed_width(value, size) / 2, size * 0.35), size=size)

    def _label(self, value, centre):
        self._centered(value, centre, LABEL_PT)

    def save(self, path: Path):
        self.doc.subset_fonts()
        self.doc.save(path, garbage=4, deflate=True)
        self.doc.close()
        return path


def _unit(v):
    length = math.hypot(v.x, v.y) or 1
    return pymupdf.Point(v.x / length, v.y / length)


def _distance(p, a, b):
    ab = b - a
    t = max(0, min(1, ((p.x - a.x) * ab.x + (p.y - a.y) * ab.y) / ((ab.x ** 2 + ab.y ** 2) or 1)))
    return math.hypot(p.x - (a.x + ab.x * t), p.y - (a.y + ab.y * t))


def draw(spec: dict, output: Path, font: Path | None = None) -> dict:
    fig = Figure(spec.get("width_pt", 220), spec["view"], font=font)
    for item in spec.get("items") or []:
        if "grid" in item:
            fig.grid(**(item["grid"] or {}))
        elif "axes" in item:
            fig.axes(**(item["axes"] or {}))
        elif "segment" in item:
            fig.segment(*item["segment"], dash=item.get("dash", False), width=item.get("width", 0.9))
        elif "polygon" in item:
            fig.polygon(item["polygon"], fill=item.get("fill"), dash=item.get("dash", False))
        elif "circle" in item:
            fig.circle(*item["circle"], dash=item.get("dash", False))
        elif "arc" in item:
            fig.arc(*item["arc"], dash=item.get("dash", False))
        elif "point" in item:
            fig.point(item["point"], item.get("label"), item.get("at", "auto"), item.get("dot", True))
        elif "angle" in item:
            fig.angle(*item["angle"], label=item.get("label"))
        elif "right_angle" in item:
            fig.right_angle(*item["right_angle"])
        elif "ticks" in item:
            fig.ticks(*item["ticks"], count=item.get("count", 1))
        elif "text" in item:
            fig.text(item["text"], item["at"], item.get("size", TEXT_PT))
        else:
            raise ValueError(f"unknown figure item {sorted(item)}")
    width, height = fig.page.rect.width, fig.height
    fig.save(output)
    return {"path": str(output), "width_pt": round(width, 1), "height_pt": round(height, 1)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("render"); r.add_argument("spec", type=Path); r.add_argument("output", type=Path)
    r.add_argument("--font", type=Path, help="the run's 明體 (RUN/fonts/TW-Sung-98_1.ttf) for Chinese labels")
    o = sub.add_parser("options", help="four option figures (A-D) drawn in one shared frame")
    o.add_argument("spec", type=Path, help='{"width_pt": 120, "view": [...], "options": {"A": [items], ...}, "common": [items]}')
    o.add_argument("--out-dir", type=Path, required=True); o.add_argument("--font", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if args.command == "render":
        result = draw(spec, args.output, args.font)
    else:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        result = {"options": {}}
        for label, items in spec["options"].items():
            single = {**spec, "items": (spec.get("common") or []) + items}
            result["options"][label] = draw(single, args.out_dir / f"option-{label}.pdf", args.font)
        result["next"] = ("compact record: \"images\": the four paths in A-D order, \"image_width_pt\": "
                          f"{spec.get('width_pt', 120)}; cap_plan.py expand makes them the options")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
