#!/usr/bin/env python3
"""會考 paper plans and item skeletons from the official 113-115 structure; never questions.

  plan   --subject 會考社會 --paper-id 20261111-01 [--year 116] [--level 高]  → plan.json for append_items.py --plan
  item   --subject 會考社會 --number 12 [--level 高]                          → one pending item and answer
  check  plan.json                                                           → plan problems before authoring

Targets come from exam_packs/會考 (official 通過率 and 鑑別度 by position, 115 sections and 題組).
A level above 會考 lowers the target pass rate; it never widens the curriculum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "exam_packs" / "會考"
SUBJECTS = ("會考國文", "會考英語", "會考數學", "會考社會", "會考自然", "會考寫作測驗")
LEVELS = ("會考", "中", "高", "極難")
LEVEL_SHIFT = {"會考": 0.0, "中": -0.10, "高": -0.20, "極難": -0.31}   # centre of each level's band
BANDS = ("簡單", "中", "中偏難", "難")
# Printed section titles of the 115 booklets.
SECTION_TITLES = {
    "會考國文": ("一、單題：（{a}～{b}題）", "二、題組：（{a}～{b}題）"),
    "會考英語": ("第一部分：單題（第{a}-{b}題，共{n}題）", "第二部分：題組（第{a}-{b}題，共{n}題）"),
    "會考數學": ("第一部分：選擇題（{a}～{b}題）", "第二部分：非選擇題（{a}～{b}題）"),
    "會考社會": ("一、單題：（{a}～{b}題）", "二、題組：（{a}～{b}題）"),
}
DOMAINS = ("地理", "歷史", "公民")
TITLES = {"會考寫作測驗": "寫作測驗"}


VOLUMES = {"第一冊": "七上", "第二冊": "七下", "第三冊": "八上", "第四冊": "八下", "第五冊": "九上", "第六冊": "九下"}
GRADE_VOLUMES = {"7": "第一、二冊（七年級）", "8": "第三、四冊（八年級）", "9": "第五、六冊（九年級）"}


def textbook_volumes(item_spec: dict) -> list[str]:
    """Printed 「可能出處」: the recorded 國中 volumes, or the grade a 數學 code names (N-8-1 → 八年級)."""
    recorded = [str(v).strip() for v in item_spec.get("textbook_volumes") or [] if str(v).strip()]
    out = []
    for value in recorded:
        volume = value[:3]
        out.append(f"{volume}（{VOLUMES[volume]}）" if volume in VOLUMES and value == volume else value)
    if not out:
        grades = sorted({c.split("-")[1] for c in item_spec.get("curriculum_codes") or []
                         if len(str(c).split("-")) == 3 and str(c).split("-")[1] in GRADE_VOLUMES})
        out = [GRADE_VOLUMES[g] for g in grades]
    return out


def solution_note(item_spec: dict) -> str:
    codes = "、".join(str(c) for c in item_spec.get("curriculum_codes") or [])
    volumes = "、".join(textbook_volumes(item_spec))
    return "；".join(part for part in (f"課綱：{codes}" if codes else "", f"可能出處：{volumes}" if volumes else "") if part)


def load(name: str) -> dict:
    return json.loads((PACK / name).read_text(encoding="utf-8"))


def form(subject: str) -> dict:
    return load("official-baseline.json")["subjects"][subject[2:]]


def position_targets(subject: str, level: str) -> dict[int, dict]:
    """{number: target p, official p range, D floor} at the chosen level."""
    if subject == "會考寫作測驗":
        return {}
    years = load(f"subjects/{subject[2:]}/blueprints/difficulty-profile.json")["curricula"]["108"]["years"]
    out = {}
    for n in range(1, max(len(y["by_position"]) for y in years.values()) + 1):
        ps = [y["by_position"][n - 1] for y in years.values() if n <= len(y["by_position"])]
        ds = [y["discrimination_by_position"][n - 1] for y in years.values()
              if n <= len(y.get("discrimination_by_position") or [])]
        centre = min(0.95, max(0.15, statistics.mean(ps) + LEVEL_SHIFT[level]))
        out[n] = {"target_p": round(centre, 2), "official_p_113_115": [min(ps), max(ps)],
                  "d_floor": 0.40, "official_d_113_115": [min(ds), max(ds)] if ds else None}
    return out


def domain_schedule(count: int, seed: str) -> list[str]:
    """Short alternating runs of 地理／歷史／公民 (115: runs of 1-5, about 18 switches)."""
    digest = hashlib.sha256(seed.encode()).digest()
    runs, order, i = [], list(DOMAINS), 0
    while sum(runs) < count:
        runs.append(1 + digest[i % len(digest)] % 4)
        i += 1
    schedule = []
    for index, run in enumerate(runs):
        schedule += [order[(index + digest[0]) % 3]] * run
    schedule = schedule[:count]
    # Balance to 25-42% each by relabelling the longest surplus run's tail.
    for _ in range(count):
        counts = {d: schedule.count(d) for d in DOMAINS}
        high, low = max(counts, key=counts.get), min(counts, key=counts.get)
        if counts[high] - counts[low] <= 2:
            break
        index = max(i for i, d in enumerate(schedule) if d == high and (i + 1 == count or schedule[i + 1] != high))
        schedule[index] = low
    return schedule


def sections(subject: str) -> list[dict]:
    current = form(subject)["current_form"]
    titles = SECTION_TITLES.get(subject)
    found = current.get("sections_115") or []
    if not titles or len(found) < 2:
        return [{"id": "s1", "title": "", "instructions": []}]   # 自然, 寫作: no printed heading
    return [{"id": f"s{i + 1}", "title": titles[i].format(a=s["first"], b=s["last"], n=s["last"] - s["first"] + 1),
             "instructions": []} for i, s in enumerate(found[:2])]


def plan(subject: str, paper_id: str, year: str = "116", level: str = "會考") -> dict:
    if subject not in SUBJECTS or level not in LEVELS:
        raise ValueError(f"subject must be one of {SUBJECTS}; level one of {LEVELS}")
    current = form(subject)["current_form"]
    name = TITLES.get(subject, subject[2:] + "科")
    metadata = {"paper_id": paper_id, "title": f"{year}年國中教育會考模擬試題 {name}", "exam": "會考",
                "subject": subject, "curriculum": "108", "generation_mode": "full-paper",
                "calibration_level": "official-113-115-structure-and-item-pass-rates",
                "cap_difficulty_level": level, "duration_minutes": current["duration_minutes"],
                "difficulty_balance_plan": {"basis": f"113-115 official 通過率 by position, level {level}",
                                            "required_bands": [], "target_counts": {b: None for b in BANDS},
                                            "shared_reading_minutes": None},
                "visual_contract": {}, "mixed_group_originality_records": []}
    slots = []
    if subject != "會考寫作測驗":
        targets = position_targets(subject, level)
        count = current["choice_items"]["reference_115"]
        groups = {n: g for g in current.get("groups_115") or [] for n in range(g[0], g[1] + 1)}
        single = [n for n in range(1, count + 1) if n not in groups]
        schedule = dict(zip(single, domain_schedule(len(single), paper_id))) if subject == "會考社會" else {}
        secs = sections(subject)
        for n in range(1, count + 1):
            slot = {"number": n, "type": "single_choice",
                    "section_id": secs[1]["id"] if len(secs) > 1 and n in groups else secs[0]["id"],
                    "group": groups.get(n), **targets.get(n, {})}
            if n in schedule:
                slot["domain"] = schedule[n]
            slots.append(slot)
        for n in range(1, current.get("constructed_items", 0) + 1):
            slots.append({"number": n, "type": "constructed_response", "section_id": "s2", "rubric": "0-3 級分"})
    return {"metadata": metadata, "instructions": [], "sections": sections(subject),
            "planning_slots": slots,
            "note": "append_items.py --plan keeps metadata, instructions and sections; planning_slots are guidance only. "
                    "Fill difficulty_balance_plan.target_counts before the first batch."}


def item(subject: str, number: int, level: str = "會考", kind: str = "single_choice") -> dict:
    slots = [s for s in plan(subject, "skeleton", level=level)["planning_slots"]
             if s["number"] == number and s["type"] == kind]
    if not slots:
        raise ValueError(f"{subject} has no {kind} slot {number}")
    slot = slots[0]
    choice = kind == "single_choice"
    steps = 3 if level in ("高", "極難") or not choice else 2
    question = {"id": f"q{number}" if choice else f"c{number}", "number": number, "section_id": slot["section_id"],
                "type": kind, "prompt": None, "group_stimulus": None, "visual_asset": None,
                **({"options": [{"label": c, "text": None} for c in "ABCD"]} if choice else {"number_display": f"{number}."}),
                "item_spec": {
                    "curriculum_codes": [], "textbook_volumes": [],
                    "cap_competency": {"context_type": None, "process": None, "real_world_anchor": None,
                                       "evidence_link": None, "prerequisite_knowledge": [], "hidden_concept": None,
                                       **({"domain": slot["domain"], "domains": [slot["domain"]]} if "domain" in slot else {}),
                                       "bridge": None},
                    **({"cap_distractors": {c: {"misconception": None, "peer_concept": None, "expected_pick_rate": None, "ruled_out_by": None}
                                          for c in "ABCD"}}
                       if choice else {}),
                    "difficulty": {"label": None},
                    "difficulty_design": {"band": None, "basis": None, "confidence": None, "short_route": None,
                                          "misconception": None, "linked_decisions": [None, None], "bottleneck": [],
                                          "expected_minutes": None, "content_sha256": None}}}
    answer = {"question_id": question["id"], "final_answer": None, "difficulty_label": None,
              "reasoning": [None] * steps, **({} if choice else {"rubric": {"3": None, "2": None, "1": None, "0": None}})}
    return {"status": "pending-authoring", "subject": subject, "level": level, "slot": slot,
            "question": question, "answer": answer,
            "rules": ["references/current-cap-form.md 品質標準 and 難度等級",
                      "cap_distractors: delete the key's row; each wrong option names its misconception and the real "
                      "neighbouring concept it borrows (三省六部 ↔ 三公九卿), never an absurd or absolute claim",
                      "hidden_concept: the term the student must infer; it may not appear in the stem, material or figure",
                      "混合考點: at least 20% of items join two domains (社會: cap_competency.domains, primary first) or two "
                      "curriculum strands, with a bridge saying why the answer needs both",
                      "figures carry evidence, never the conclusion; options alike in length and voice",
                      f"reasoning: at least {steps} steps from learned 國中 knowledge, then name every option (A)-(D) and why "
                      "each distractor fails; at least two linked_decisions",
                      "cap_distractors.*.expected_pick_rate: predicted share choosing each wrong option, at least 0.05",
                      "textbook_volumes: the 國中 volume(s) the concepts are taught in, e.g. [\"第三冊\"] (第一冊=七上 … 第六冊=九下); "
                      "數學 may leave it empty, the code's grade is printed; the solution prints 課綱 and 可能出處"]}


def check(plan_data: dict) -> list[str]:
    errors = []
    meta = plan_data.get("metadata") or {}
    subject = meta.get("subject")
    if meta.get("exam") != "會考" or subject not in SUBJECTS:
        return ["metadata.exam must be 會考 and metadata.subject a prefixed 會考 key"]
    if meta.get("cap_difficulty_level", "會考") not in LEVELS:
        errors.append(f"cap_difficulty_level must be one of {'、'.join(LEVELS)}")
    if meta.get("generation_mode") != "full-paper":
        errors.append('generation_mode must be "full-paper" so whole-paper floors run')
    slots = [s for s in plan_data.get("planning_slots") or [] if s.get("type") == "single_choice"]
    counts = (meta.get("difficulty_balance_plan") or {}).get("target_counts") or {}
    if subject != "會考寫作測驗":
        if any(not isinstance(counts.get(b), int) for b in BANDS):
            errors.append("difficulty_balance_plan.target_counts needs a count for each of 簡單／中／中偏難／難")
        elif sum(counts.values()) != len(slots) + sum(1 for s in plan_data.get("planning_slots") or []
                                                      if s.get("type") == "constructed_response"):
            errors.append("difficulty_balance_plan.target_counts must add up to the planned items")
    if subject == "會考社會":
        domains = [s.get("domain") for s in slots if not s.get("group")]
        for d in DOMAINS:
            if domains and not 0.25 <= domains.count(d) / len(domains) <= 0.42:
                errors.append(f"{d} holds {domains.count(d)} of {len(domains)} 單題 (25-42% each)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan"); p.add_argument("--subject", required=True, choices=SUBJECTS)
    p.add_argument("--paper-id", required=True); p.add_argument("--year", default="116")
    p.add_argument("--level", default="會考", choices=LEVELS); p.add_argument("--output", type=Path)
    i = sub.add_parser("item"); i.add_argument("--subject", required=True, choices=SUBJECTS)
    i.add_argument("--number", type=int, required=True); i.add_argument("--level", default="會考", choices=LEVELS)
    i.add_argument("--constructed", action="store_true", help="數學 非選擇題 slot")
    c = sub.add_parser("check"); c.add_argument("plan", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        result = plan(args.subject, args.paper_id, args.year, args.level)
        if args.output:
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {"status": "plan-written", "output": str(args.output), "check": check(result)}
    elif args.command == "item":
        result = item(args.subject, args.number, args.level, "constructed_response" if args.constructed else "single_choice")
    else:
        errors = check(json.loads(args.plan.read_text(encoding="utf-8")))
        result = {"status": "pass" if not errors else "fix-before-authoring", "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
