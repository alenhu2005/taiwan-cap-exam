#!/usr/bin/env python3
"""Content coverage of official 會考 papers (113-115), per subject, as closed unit lists.

A hosted 會考數學 paper (M1111, 2026-11) put five of 25 items on 統計／機率 and none on 圓、
相似形、多項式 or 二次方根, although every official year has them: the plan only drew a random
topic per slot. Each item now records `item_spec.cap_unit` (自然: `cap_competency.domain`) from the
list below; `cap_plan.py plan` schedules the units so a paper starts inside the official ranges,
and `validate_cap_quality.py` checks the finished paper.

Counts are choice items classified by hand from the official booklets (113/114/115, maintainer
review 2026-11; 自然 domains by keyword and spot check, so its ranges are wider). A range is the
official minimum and maximum, widened by one where three years differ, so a paper may differ
from any one year without leaving the official pattern.
"""
from __future__ import annotations

import hashlib
import random

# 數學 choice items 1-25: (113, 114, 115)
MATH_OFFICIAL = {
    "數與運算": (6, 6, 5), "二次方根": (1, 1, 1), "數列": (1, 0, 1), "方程式與不等式": (4, 3, 4),
    "多項式與一元二次方程式": (1, 3, 2), "坐標與函數": (2, 2, 2), "平面幾何": (4, 3, 4),
    "相似形與三角形三心": (1, 3, 1), "圓": (2, 1, 2), "立體與空間": (1, 1, 1), "統計": (1, 1, 1), "機率": (1, 1, 1),
}
# 國文 items 1-42: 語文知識 = 字音字形字義、詞語成語、標點、六書字體、題辭稱謂；詩歌 = 古典詩詞曲與現代詩；
# 文言文本 = 文言散文、筆記、史傳；白話文學 = 白話散文、小說、劇本；資訊與圖表 = 說明議論、資料、海報貼文、圖表。
CHINESE_OFFICIAL = {"語文知識": (9, 7, 8), "詩歌": (2, 4, 4), "文言文本": (10, 10, 10), "白話文學": (6, 7, 6),
                    "資訊與圖表": (15, 14, 14)}
# 英語 items 1-43: 單題 (113: 1-21; 114, 115: 1-19) are 字彙 or 文法; 題組 by text type, the last
# group a 克漏字 passage every year.
ENGLISH_OFFICIAL = {"字彙": (None, None, 9), "文法": (None, None, 10), "實用文本": (4, 3, 5), "圖文對話": (0, 5, 2),
                    "記敘文本": (4, 2, 5), "說明文本": (10, 8, 8), "克漏字": (4, 6, 4)}

# Mean printed position of each 數學 unit in 113-115 (circles and similar triangles close the paper,
# radicals, polynomials and solids open it); the plan orders units by it with a random jitter.
MATH_MEAN_POSITION = {"數與運算": 13, "二次方根": 7, "數列": 11, "方程式與不等式": 13, "多項式與一元二次方程式": 8.5,
                      "坐標與函數": 11.7, "平面幾何": 14.6, "相似形與三角形三心": 19.6, "圓": 19.6, "立體與空間": 5.3,
                      "統計": 7.3, "機率": 7}
POSITION_JITTER = 6

UNIT_RANGES = {
    "會考數學": {"數與運算": (4, 7), "二次方根": (1, 2), "數列": (0, 2), "方程式與不等式": (2, 5),
                 "多項式與一元二次方程式": (1, 4), "坐標與函數": (2, 3), "平面幾何": (2, 5), "相似形與三角形三心": (1, 4),
                 "圓": (1, 3), "立體與空間": (1, 2), "統計": (1, 2), "機率": (1, 2)},
    "會考國文": {"語文知識": (6, 10), "詩歌": (2, 5), "文言文本": (9, 12), "白話文學": (5, 8), "資訊與圖表": (12, 16)},
    "會考英語": {"字彙": (7, 12), "文法": (7, 12), "實用文本": (2, 6), "圖文對話": (0, 5), "記敘文本": (2, 6),
                 "說明文本": (7, 11), "克漏字": (4, 6)},
}
# Units that are one decision by design (a word, a structure): official 英語 1-19 and 國文 語文知識
# items are, so the linked-decision rule skips them.
SINGLE_DECISION_UNITS = {"字彙", "文法", "語文知識"}
SINGLE_UNITS = {"會考英語": ("字彙", "文法")}
GROUP_UNITS = {"會考英語": ("實用文本", "圖文對話", "記敘文本", "說明文本"),
               "會考國文": ("詩歌", "文言文本", "白話文學", "資訊與圖表")}
DATA_UNITS_MAX = {"會考數學": (("統計", "機率"), 3)}   # official 2 a year; M1111 printed 5
# 自然 (cap_competency.domain), share of all items. 115 by hand 13/26/11; 113-114 by keyword.
SCIENCE_SHARES = {"生物": (0.22, 0.38), "理化": (0.42, 0.58), "地球科學": (0.14, 0.26)}
SCIENCE_OFFICIAL = {"生物": (21, 11, 13), "理化": (22, 28, 26), "地球科學": (7, 11, 11)}


def unit_of(question: dict, subject: str) -> str | None:
    spec = question.get("item_spec") or {}
    if subject == "會考自然":
        record = spec.get("cap_competency") or {}
        return (record.get("domains") or [None])[0] or record.get("domain") or spec.get("domain")
    return spec.get("cap_unit")


def unit_errors(subject: str, questions: list[dict], *, full: bool = True) -> list[str]:
    """Missing or unknown units per item, and (full papers) counts outside the official ranges."""
    choice = [q for q in questions if q.get("type") == "single_choice"]
    errors: list[str] = []
    if subject == "會考自然":
        domains = [unit_of(q, subject) for q in choice]
        if full and choice and all(d in SCIENCE_SHARES for d in domains):
            for domain, (low, high) in SCIENCE_SHARES.items():
                share = domains.count(domain) / len(domains)
                if not low <= share <= high:
                    errors.append(f"{domain} holds {domains.count(domain)} of {len(domains)} items ({share:.0%}); official "
                                  f"113-115 keep it at {low:.0%}-{high:.0%} (cap_competency.domain on every item, 題組 too)")
        elif full and choice:
            missing = [q.get("number") for q, d in zip(choice, domains) if d not in SCIENCE_SHARES]
            errors.append(f"items {missing[:12]} need cap_competency.domain (生物／理化／地球科學), 題組 items too")
        return errors
    ranges = UNIT_RANGES.get(subject)
    if not ranges:
        return errors
    units = [unit_of(q, subject) for q in choice]
    unknown = [q.get("number") for q, u in zip(choice, units) if u not in ranges]
    if unknown:
        errors.append(f"items {unknown[:12]}: item_spec.cap_unit must be one of {'、'.join(ranges)} "
                      "(cap_plan.py plan assigns one per slot)")
        return errors
    if not full:
        return errors
    for unit, (low, high) in ranges.items():
        count = units.count(unit)
        if not low <= count <= high:
            errors.append(f"{count} items on {unit}; official 113-115 papers hold {low}-{high} "
                          f"({'more' if count < low else 'fewer'} needed): a 會考 paper covers the units every year covers")
    if subject in DATA_UNITS_MAX:
        names, cap = DATA_UNITS_MAX[subject]
        count = sum(units.count(n) for n in names)
        if count > cap:
            errors.append(f"{count} items on {'＋'.join(names)} (official 2 a year, at most {cap})")
    return errors


def _official_mean(subject: str, unit: str) -> float:
    table = {"會考數學": MATH_OFFICIAL, "會考國文": CHINESE_OFFICIAL, "會考英語": ENGLISH_OFFICIAL}[subject]
    values = [v for v in table.get(unit, ()) if v is not None]
    return sum(values) / len(values) if values else 1.0


def _counts(subject: str, total: int, rng: random.Random, units=None) -> dict[str, int]:
    """Counts within the ranges that add up to `total`, leaning on the official means."""
    ranges = {u: r for u, r in UNIT_RANGES[subject].items() if units is None or u in units}
    counts = {u: low for u, (low, high) in ranges.items()}
    while sum(counts.values()) < total:
        open_ = [u for u in ranges if counts[u] < ranges[u][1]]
        if not open_:
            break
        weights = [max(0.2, _official_mean(subject, u) - counts[u] + 0.5) for u in open_]
        counts[rng.choices(open_, weights)[0]] += 1
    return counts


def schedule(subject: str, slots: list[dict], seed: str) -> dict[int, str]:
    """{slot number: unit} for the choice slots of a plan; 題組 members share one unit (國文、英語)."""
    if subject not in UNIT_RANGES and subject != "會考自然":
        return {}
    choice = [s for s in slots if s.get("type") == "single_choice"]
    groups: dict[tuple, list[int]] = {}
    for s in choice:
        if s.get("group"):
            groups.setdefault(tuple(s["group"]), []).append(s["number"])
    singles = [s["number"] for s in choice if not s.get("group")]
    for attempt in range(200):
        rng = random.Random(hashlib.sha256(f"{seed}:units:{attempt}".encode()).digest())
        out: dict[int, str] = {}
        if subject == "會考自然":
            target = {d: round(len(choice) * (low + high) / 2) for d, (low, high) in SCIENCE_SHARES.items()}
            target["理化"] += len(choice) - sum(target.values())
            left = dict(target)
            for members in groups.values():
                domain = rng.choices(list(left), [max(0, left[d] - len(members) + 1) + 0.01 for d in left])[0]
                for n in members:
                    out[n] = domain
                left[domain] -= len(members)
            pool = [d for d, k in left.items() for _ in range(max(0, k))]
            rng.shuffle(pool)
            pool += ["理化"] * (len(singles) - len(pool))
            out.update(zip(singles, pool))
        elif subject in GROUP_UNITS:
            counts = _counts(subject, len(choice), rng)
            ordered = sorted(groups.values())
            if subject == "會考英語" and ordered:
                cloze = ordered.pop()          # the last group is the 克漏字 passage every year
                for n in cloze:
                    out[n] = "克漏字"
                counts["克漏字"] -= len(cloze)
            for members in ordered:
                allowed = [u for u in GROUP_UNITS[subject] if counts.get(u, 0) >= len(members)] or list(GROUP_UNITS[subject])
                unit = rng.choices(allowed, [counts.get(u, 0) + 0.1 for u in allowed])[0]
                for n in members:
                    out[n] = unit
                counts[unit] = counts.get(unit, 0) - len(members)
            pool = [u for u, k in counts.items() for _ in range(max(0, k))
                    if subject != "會考英語" or u in SINGLE_UNITS[subject]]
            if subject == "會考英語":
                pool = (pool + list(SINGLE_UNITS[subject]) * len(singles))[:len(singles)]
            rng.shuffle(pool)
            out.update(zip(singles, pool))
        else:
            counts = _counts(subject, len(choice), rng)
            pool = [u for u, k in counts.items() for _ in range(k)]
            rng.shuffle(pool)
            pool.sort(key=lambda u: MATH_MEAN_POSITION.get(u, 12) + rng.uniform(-POSITION_JITTER, POSITION_JITTER))
            out.update(zip(sorted(s["number"] for s in choice), pool))
        trial = [{"type": "single_choice", "number": n,
                  "item_spec": {"cap_unit": u, "cap_competency": {"domain": u}}} for n, u in out.items()]
        if len(out) == len(choice) and not unit_errors(subject, trial):
            return out
    return out
