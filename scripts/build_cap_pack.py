#!/usr/bin/env python3
"""Build the 會考 Exam Pack's aggregate data from official 113-115 documents.

Input: a folder with one sub-folder per ROC year (113, 114, 115), each holding the
official booklets and the 各題通過率 table downloaded from cap.rcpet.edu.tw
(chinese.pdf, english.pdf, math.pdf, social.pdf, science.pdf, writing.pdf,
passrate.pdf, plus ids.txt mapping each file to its official Google Drive id).

Output (aggregate only, never question text):
  exam_packs/會考/official-baseline.json            form structure per year and source hashes
  exam_packs/會考/metadata/hosted-page-metrics.json  bottom-void density of every official inner page
  exam_packs/會考/subjects/<科目>/blueprints/difficulty-profile.json   official per-position 通過率
  exam_packs/會考/subjects/<科目>/blueprints/writer-blueprint.json     form contract and calibration status

英語 is the reading booklet only: the listening section is out of scope for this pack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path

import pymupdf

from inspect_hosted_pdf import bottom_void

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "exam_packs" / "會考"
YEARS = (113, 114, 115)
FILES = {"國文": "chinese", "英語": "english", "數學": "math", "社會": "social", "自然": "science", "寫作測驗": "writing"}
PASSRATE_COLUMN = {"國文": "國文", "英語": "英語(閱讀)", "數學": "數學", "社會": "社會", "自然": "自然"}
DRIVE_VIEW = "https://drive.google.com/file/d/{id}/view"
YEAR_PAGE = "https://cap.rcpet.edu.tw/exam/{year}/{year}exam.html"
# 會考 等級加標示 bands are set per year on raw scores; for item writing we use the
# conventional pass-rate bands (易 ≥ .70, 中 .40-.70, 難 < .40).
BANDS = (("易", 0.70, 1.01), ("中", 0.40, 0.70), ("難", 0.0, 0.40))
GROUP_PATTERNS = (
    re.compile(r"回答\s*第?\s*(\d+)\s*(?:～|~|至|-)\s*(\d+)\s*題"),
    re.compile(r"\(\s*(\d+)\s*[-–]\s*(\d+)\s*\)"),          # 英語 「(20-21)」
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def full_text(path: Path) -> str:
    with pymupdf.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)


SPACES = re.compile("[ \u2006\t]+")


def number(pattern: str, text: str) -> int | None:
    """The count a cover states, or None when the cover text is not extractable (113 英語)."""
    match = re.search(pattern, SPACES.sub(" ", text))
    return int(match.group(1)) if match else None


def booklet_structure(path: Path, subject: str) -> dict:
    """Counts the cover states and the section/group ranges the booklet prints."""
    text = full_text(path)
    flat = SPACES.sub(" ", text)
    with pymupdf.open(path) as doc:
        pages = len(doc)
    stated = number(r"共\s*(\d+)\s*頁", flat)
    result = {"booklet_pages": pages,
              "inner_pages": stated or pages - 1,
              "duration_minutes": number(r"共\s*(\d+)\s*分鐘", flat)}
    if stated is None:
        result["cover_text"] = "not-extractable; counts taken from the booklet and the official pass-rate table"
    if subject == "寫作測驗":
        result.update({"tasks": number(r"僅有\s*(\d+)\s*題", flat), "question_types": ["guided_writing"]})
        return result
    if subject == "數學":
        result["choice_items"] = number(r"第一部分有\s*(\d+)\s*題選擇題", flat)
        result["constructed_items"] = number(r"第二部分有\s*(\d+)\s*題非選擇題", flat)
    else:
        result["choice_items"] = number(r"有\s*(\d+)\s*題\s*選擇題", flat)
        result["constructed_items"] = 0
    limit = result["choice_items"] or 99
    sections = []
    for match in re.finditer(r"(?:[一二]、|第[一二]部分：)\s*(單題|題組|選擇題|非選擇題)\s*[：:]?\s*[（(]\s*第?\s*(\d+)\s*[～~\-]\s*(\d+)", flat):
        sections.append({"title": match.group(1), "first": int(match.group(2)), "last": int(match.group(3))})
    result["sections"] = sections
    # Distinct figure/table labels the booklet prints: 圖(一)、表(三)… (answer-bearing visuals).
    result["figures"] = len(set(re.findall(r"圖\s*[（(]\s*([一二三四五六七八九十]+)\s*[)）]", flat)))
    result["tables"] = len(set(re.findall(r"表\s*[（(]\s*([一二三四五六七八九十]+)\s*[)）]", flat)))
    groups = sorted({(int(a), int(b)) for pattern in GROUP_PATTERNS for a, b in pattern.findall(flat)
                     if int(a) < int(b) <= limit and int(b) - int(a) < 8})
    result["groups"] = [list(g) for g in groups]
    result["group_items"] = sum(b - a + 1 for a, b in groups)
    return result


def passrates(path: Path) -> dict[str, list[float]]:
    """{column: [p of item 1, 2, ...]} read by x position (columns end at different rows)."""
    out: dict[str, dict[int, float]] = {}
    with pymupdf.open(path) as doc:
        for page in doc:
            words = page.get_text("words")
            headers = {w[4]: (w[0] + w[2]) / 2 for w in words if w[4] in {*PASSRATE_COLUMN.values(), "英語(聽力)"}}
            if not headers:
                continue
            rows: dict[float, list] = {}
            for w in words:
                rows.setdefault(round(w[1]), []).append(w)
            for row in rows.values():
                label = min(row, key=lambda w: w[0])
                if not label[4].isdigit():
                    continue
                item = int(label[4])
                for w in row:
                    if w is label or not re.fullmatch(r"[01]\.\d\d", w[4]):
                        continue
                    centre = (w[0] + w[2]) / 2
                    column = min(headers, key=lambda h: abs(headers[h] - centre))
                    out.setdefault(column, {})[item] = float(w[4])
    result = {}
    for column, values in out.items():
        items = sorted(values)
        if items != list(range(1, len(items) + 1)):
            raise ValueError(f"{path.name}: {column} item numbers are not contiguous")
        result[column] = [values[i] for i in items]
    return result


def band_of(p: float) -> str:
    return next(name for name, low, high in BANDS if low <= p < high)


def summary(values: list[float]) -> dict:
    ordered = sorted(values)
    q = statistics.quantiles(ordered, n=4)
    bands = {name: sum(1 for v in values if band_of(v) == name) for name, *_ in BANDS}
    thirds = [values[i * len(values) // 3:(i + 1) * len(values) // 3] for i in range(3)]
    return {"items": len(values), "mean_p": round(statistics.mean(values), 3), "sd_p": round(statistics.pstdev(values), 3),
            "min_p": min(values), "q1_p": round(q[0], 3), "median_p": round(q[1], 3), "q3_p": round(q[2], 3),
            "max_p": max(values), "band_counts": bands,
            "band_shares": {k: round(v / len(values), 3) for k, v in bands.items()},
            "position_thirds_mean_p": [round(statistics.mean(t), 3) for t in thirds]}


def page_metrics(path: Path, subject: str, year: int) -> list[dict]:
    rows = []
    digest = sha(path)
    with pymupdf.open(path) as doc:
        count = len(doc)
        for index in range(1, count):
            page = doc[index]
            text = page.get_text()
            if subject == "數學" and "參考公式" in text:
                role = "formula"
            elif len(text.strip()) < 40 or "會考寫作測驗" in text:
                role = "blank"
            else:
                role = "body"
            box = [64, 50, page.rect.width - 60, 760]
            rows.append({"subject": subject, "roc_year": year, "page": index + 1, "page_role": role,
                         "source_sha256": digest, "bottom_void": bottom_void(page, box) if role == "body" else None})
    return rows


def load_ids(folder: Path) -> dict[str, str]:
    ids = {}
    path = folder / "ids.txt"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                name, file_id = line.split()
                ids[name] = file_id
    return ids


def build(source: Path) -> dict:
    baseline_subjects: dict[str, dict] = {s: {"years": {}} for s in FILES}
    sources, metrics = [], []
    profiles: dict[str, dict] = {s: {} for s in PASSRATE_COLUMN}
    for year in YEARS:
        folder = source / str(year)
        ids = load_ids(folder)
        for subject, stem in FILES.items():
            path = folder / f"{stem}.pdf"
            structure = booklet_structure(path, subject)
            baseline_subjects[subject]["years"][str(year)] = structure
            sources.append({"roc_year": year, "subject": subject, "document": "試題本",
                            "url": DRIVE_VIEW.format(id=ids[stem]) if stem in ids else YEAR_PAGE.format(year=year),
                            "listing": YEAR_PAGE.format(year=year), "bytes": path.stat().st_size, "sha256": sha(path)})
            metrics.extend(page_metrics(path, subject, year))
        rates_path = folder / "passrate.pdf"
        sources.append({"roc_year": year, "subject": "全科", "document": "各題通過率",
                        "url": DRIVE_VIEW.format(id=ids["passrate"]) if "passrate" in ids else YEAR_PAGE.format(year=year),
                        "listing": YEAR_PAGE.format(year=year), "bytes": rates_path.stat().st_size, "sha256": sha(rates_path)})
        rates = passrates(rates_path)
        discrim_path = folder / "discrim.pdf"
        discrimination = passrates(discrim_path) if discrim_path.is_file() else {}
        if discrimination:
            sources.append({"roc_year": year, "subject": "全科", "document": "各題鑑別度",
                            "url": DRIVE_VIEW.format(id=ids["discrim"]) if "discrim" in ids else YEAR_PAGE.format(year=year),
                            "listing": YEAR_PAGE.format(year=year), "bytes": discrim_path.stat().st_size, "sha256": sha(discrim_path)})
        for subject, column in PASSRATE_COLUMN.items():
            values = rates[column]
            structure = baseline_subjects[subject]["years"][str(year)]
            if structure["choice_items"] is None:
                structure["choice_items"] = len(values)
                structure["groups"] = [g for g in structure["groups"] if g[1] <= len(values)]
                structure["group_items"] = sum(b - a + 1 for a, b in structure["groups"])
            expected = structure["choice_items"]
            if len(values) != expected:
                raise ValueError(f"{year} {subject}: {len(values)} pass rates for {expected} choice items")
            structure = baseline_subjects[subject]["years"][str(year)]
            grouped = {n for a, b in structure.get("groups", []) for n in range(a, b + 1)}
            d_values = discrimination.get(column)
            profiles[subject][str(year)] = {
                "by_position": values, "summary": summary(values),
                **({"discrimination_by_position": d_values, "discrimination_summary": {
                    "mean_d": round(statistics.mean(d_values), 3), "min_d": min(d_values), "max_d": max(d_values),
                    "share_d_at_least_0_40": round(sum(d >= 0.40 for d in d_values) / len(d_values), 3),
                    "share_d_below_0_30": round(sum(d < 0.30 for d in d_values) / len(d_values), 3)}}
                   if d_values and len(d_values) == len(values) else {}),
                "standalone_mean_p": round(statistics.mean([v for i, v in enumerate(values, 1) if i not in grouped] or [0]), 3),
                "group_mean_p": round(statistics.mean([v for i, v in enumerate(values, 1) if i in grouped]), 3) if grouped else None,
            }
    return {"subjects": baseline_subjects, "sources": sources, "metrics": metrics, "profiles": profiles}


def form_contract(subject: str, years: dict) -> dict:
    """The current-form envelope: the 113-115 range, the 115 booklet as the reference."""
    latest = years[str(max(YEARS))]
    if subject == "寫作測驗":
        return {"tasks": 1, "duration_minutes": latest["duration_minutes"], "question_types": ["guided_writing"],
                "rules": ["一題引導寫作，題目提供文字或圖文材料與明確的寫作任務",
                          "不必訂題；不得使用詩歌體；不可在文中洩漏私人身分",
                          "評分為一至六級分（官方寫作測驗評分規準），不另列題目分數"]}
    choice = [years[y]["choice_items"] for y in years]
    groups = [g for y in years for g in years[y].get("groups", [])]
    sizes = sorted(b - a + 1 for a, b in groups)
    return {
        "choice_items": {"min": min(choice), "max": max(choice), "reference_115": latest["choice_items"]},
        "constructed_items": latest["constructed_items"],
        "options_per_choice_item": 4, "option_labels": ["(A)", "(B)", "(C)", "(D)"],
        "answer_mode": "單選題（四選一），答錯不倒扣",
        "duration_minutes": latest["duration_minutes"] or max(
            years[y]["duration_minutes"] for y in years if years[y].get("duration_minutes")),
        "inner_pages_115": latest["inner_pages"],
        "sections_115": latest.get("sections", []),
        "groups_115": latest.get("groups", []),
        "group_items_by_year": {y: years[y].get("group_items", 0) for y in years},
        "group_size_counts": {str(n): sizes.count(n) for n in sorted(set(sizes))},
    }


def write(data: dict) -> list[Path]:
    written = []

    def save(path: Path, value) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        written.append(path)

    subjects = {}
    for subject, record in data["subjects"].items():
        base = {"國文": ["單題", "題組"], "英語": ["閱讀"], "數學": ["選擇題", "非選擇題"], "社會": ["單題", "題組"],
                "自然": ["自然"], "寫作測驗": ["引導寫作"]}[subject]
        types = {"數學": ["single_choice", "constructed_response"], "寫作測驗": ["guided_writing"]}.get(subject, ["single_choice"])
        subjects[subject] = {"sections": base, "allowed_question_types": types,
                             **({"domains": ["歷史", "地理", "公民"]} if subject == "社會" else {}),
                             **({"domains": ["生物", "理化", "地球科學"]} if subject == "自然" else {}),
                             **({"excluded_sections": ["聽力"], "excluded_reason": "本 Skill 只製作英語閱讀題本；聽力需要音檔，不在範圍內。"}
                                if subject == "英語" else {}),
                             "current_form": form_contract(subject, record["years"]),
                             "years": record["years"]}
    save(PACK / "official-baseline.json", {
        "verified_on": "2026-11-10", "calibration_level": "official-113-115-structure-and-item-pass-rates",
        "curriculum": "108", "scope": "十二年國民基本教育課程綱要第四學習階段學習表現及學習內容",
        "structure_status": "verified",
        "structure_basis": "Counts, sections, groups, durations and pages parsed from the official 113-115 booklets "
                           "(scripts/build_cap_pack.py); every document is bound by SHA-256 below.",
        "subjects": subjects, "sources": data["sources"],
        "official_sites": ["https://cap.rcpet.edu.tw/", "https://cap.rcpet.edu.tw/examination.html"],
        "warning": "各年度題數會在官方範圍內變動；以 113-115 範圍為現行卷型，115 題本為版型與題數參考。",
    })
    save(PACK / "metadata" / "hosted-page-metrics.json", {
        "schema_version": 1, "exam": "會考", "algorithm": "inspect_hosted_pdf.bottom_void",
        "body_box_pt": [64, 50, "page width - 60", 760], "pages": data["metrics"]})
    for subject, years in data["profiles"].items():
        pooled = [p for y in years.values() for p in y["by_position"]]
        save(PACK / "subjects" / subject / "blueprints" / "difficulty-profile.json", {
            "schema_version": 1, "exam": "會考", "subject": subject, "statistic": "official 各題通過率 (p)",
            "bands": {name: [low, min(high, 1.0)] for name, low, high in BANDS},
            "curricula": {"108": {"status": "ready", "years": years, "pooled_113_115": summary(pooled),
                                  "source": "cap.rcpet.edu.tw 各題通過率 113-115"}}})
    for subject in FILES:
        record = subjects[subject]
        profile = data["profiles"].get(subject)
        pooled = summary([p for y in profile.values() for p in y["by_position"]]) if profile else None
        save(PACK / "subjects" / subject / "blueprints" / "writer-blueprint.json", {
            "schema_version": 1, "exam": "會考", "subject": subject, "purpose": "aggregate-only writer envelope",
            "forbidden_uses": ["copying or paraphrasing official items, passages, figures or option sets",
                               "reusing an official item's solution path with new names or numbers"],
            "form_contract": record["current_form"],
            "difficulty_targets": ({"mean_p": [round(pooled["mean_p"] - .05, 2), round(pooled["mean_p"] + .05, 2)],
                                    "band_shares_113_115": pooled["band_shares"],
                                    "position_thirds_mean_p": pooled["position_thirds_mean_p"],
                                    "rule": "易題在前、難題在後的大致趨勢；題組可回到中等難度。"} if pooled else
                                   {"rule": "寫作以六級分規準評閱；命題時確保題旨清楚、各級分都有可區辨的表現空間。"}),
            "calibration_by_curriculum": {"108": {
                "status": "ready",
                "basis": "official-113-115-structure" + ("-and-item-pass-rates" if pooled else ""),
                "limitations": ["Pass rates describe official items; they are targets, not measured difficulty of new items."] +
                               (["Constructed-response 級分 statistics are not modelled; review with the official rubric."]
                                if subject == "數學" else [])}},
        })
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    written = write(build(args.source_dir))
    print(json.dumps({"written": [p.relative_to(ROOT).as_posix() for p in written]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
