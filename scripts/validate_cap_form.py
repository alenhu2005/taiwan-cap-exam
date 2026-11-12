#!/usr/bin/env python3
"""Structural form contract for 國中教育會考 papers (the 會考 booklets this Skill makes).

Checks what the printed 會考 form fixes: the subject key, the item counts within the
official 考試說明 ranges, four (A)-(D) options per selected-response item with one key,
contiguous numbering, item groups of 2-7, 數學's two 非選擇題, 寫作測驗's single task,
and no 英語 listening items (out of scope). It never judges content quality or difficulty.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "exam_packs" / "會考" / "official-baseline.json"
# 115 學年度 考試說明 (各考區簡章「考試科目及題型」): selected-response counts per booklet.
OFFICIAL_RANGES = {"會考國文": (38, 46), "會考英語": (40, 45), "會考數學": (23, 28), "會考社會": (50, 60), "會考自然": (45, 55)}
CONSTRUCTED = {"會考數學": 2}
CAP_SUBJECTS = (*OFFICIAL_RANGES, "會考寫作測驗")
LABELS = ("A", "B", "C", "D")
LONGEST_KEY_SHARE = 0.05   # official 會考社會 113-115: 0-3 a year (0-7%); target above official
# Official best year per subject (113-115 measured 2026-11): 國文 2/42, 數學 0/25, 自然 2/50, 社會 0/54,
# 英語 6/43 (English words differ in length by nature: 10/43 in 115).
LONGEST_KEY_BY_SUBJECT = {"會考英語": 0.14}
CHOICE_TYPES = {"single_choice"}
CONSTRUCTED_TYPES = {"constructed_response", "short_answer"}
WRITING_TYPES = {"guided_writing", "essay", "constructed_response"}
# 素養導向: official 會考 items set a concept in a real situation (a 2024 typhoon's farm losses, a
# speedometer regulation, a school notice) and ask students to extract, integrate, infer or apply.
SITUATED_CONTEXTS = {"生活情境", "社會議題", "科學探究", "跨領域"}
CONTEXT_TYPES = SITUATED_CONTEXTS | {"學科知識", "文本閱讀"}
PROCESSES = {"擷取訊息", "統整解釋", "推論", "應用", "評鑑"}
# Measured on 113-115 (maintainer review 2026-11): 國文 about 30% (posts, ads, data, notices; the rest
# reads literary and classical texts), 英語 about 55% (題組 texts; 單題 are word and structure items),
# 數學 33-41% (115: 文旦、細菌、書店、用電量、時速錶、馬拉松、沙發), 自然 70-80%. A math paper written
# at 89% situated (M1111) dropped the bare computation, geometry and judgement items every official
# paper has, so 數學 also has a ceiling.
SITUATED_SHARE = {"會考國文": 0.30, "會考英語": 0.50, "會考數學": 0.30, "會考社會": 0.70, "會考自然": 0.70}
SITUATED_MAX = {"會考數學": 0.60}
# Printed disclaimers that announce an invented or classroom-only world (hosted 學測 papers
# printed 「教學模型」「非 NASA 數據」「虛構小鎮」); real, checkable situations only.
# 國中 scope: 108 課綱 第四學習階段 learning-content codes (自然 Ea-IV-1, 社會 歷Ha-IV-1, 國文 Ab-IV-1)
# or 數學 grade codes N-7-1 … D-9-3. Senior-high codes (…-V-…, N-10-1, 10A) are out of scope at every level.
STAGE_IV_CODE = re.compile(r"^[^\s]*[A-Za-z]{1,2}-IV-\d+$|^[NSGARFD]-[789]-\d+$")
CAP_LEVELS = ("會考", "中", "高", "極難")
# Minimum written derivation steps in each answer: harder levels must show every link.
MIN_STEPS = {"會考": 2, "中": 2, "高": 3, "極難": 3}
DISCLAIMERS = re.compile(r"虛構|假想情境|假設性資料|教學模型|非真實|僅供練習|模擬數據")


def _label(option) -> str:
    raw = str(option.get("label", "") if isinstance(option, dict) else "")
    return re.sub(r"[()（）\s]", "", raw)


# 寫作測驗 113-115 print the same frame: the opening line, the material (headlines, a picture and a word
# bank, or a short paragraph), the questions to think about, a task joining 經驗 or 見聞, and three
# notes in this order. The 六級分 rubric scores four dimensions; the solution explains each.
WRITING_OPENING = re.compile(r"^\s*請先閱讀以下資訊，並(?:按|依據?)題意要求完成一篇文章。")
WRITING_NOTES = ("※不必訂題", "※不可在文中洩漏私人身分", "※不可使用詩歌體")
WRITING_RUBRIC = ("立意取材", "結構組織", "遣詞造句", "錯別字")


def writing_task_errors(task: dict, answer: dict) -> list[str]:
    errors = []
    prompt = str(task.get("prompt") or "")
    flat = re.sub(r"\s", "", prompt)
    if not WRITING_OPENING.match(prompt):
        errors.append("寫作測驗 opens 「請先閱讀以下資訊，並依據題意要求完成一篇文章。」 as 113-115 do")
    positions = [flat.find(note) for note in WRITING_NOTES]
    if -1 in positions or positions != sorted(positions):
        errors.append("寫作測驗 ends with the three notes in the official order: " + " ".join(WRITING_NOTES))
    if not re.search(r"經驗|見聞", flat) or "寫下" not in flat:
        errors.append("寫作測驗 asks the writer to join their own 經驗 or 見聞 and 寫下 their 感受、想法 or 觀察 "
                      "(113-115 task wording)")
    if re.search(r"題目[：:]", flat):
        errors.append("寫作測驗 prints no title (※不必訂題): give material and a task, not 「題目：」")
    explained = " ".join(str(step) for step in answer.get("reasoning") or []) + str(answer.get("final_answer") or "")
    missing = [d for d in WRITING_RUBRIC if d not in explained]
    if missing:
        errors.append(f"寫作測驗 solution explains the 級分 by the official dimensions; missing {'、'.join(missing)} "
                      "(立意取材、結構組織、遣詞造句、錯別字格式與標點符號), with a 審題 and 取材 guide")
    return errors


def full_paper_minimum(subject: str) -> int:
    if subject == "會考寫作測驗":
        return 1
    return OFFICIAL_RANGES[subject][0]


def validate_exam(exam: dict, *, full: bool = True, asset_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    metadata = exam.get("metadata") or {}
    subject = metadata.get("subject")
    if metadata.get("exam") != "會考":
        errors.append("metadata.exam must be 會考")
    if subject not in CAP_SUBJECTS:
        return errors + [f"metadata.subject must be one of {', '.join(CAP_SUBJECTS)} (got {subject!r})"]
    questions = [q for q in exam.get("questions") or [] if isinstance(q, dict)]
    answers = {a.get("question_id"): a for a in exam.get("answers") or [] if isinstance(a, dict)}
    if subject == "會考寫作測驗":
        tasks = [q for q in questions if q.get("type") in WRITING_TYPES]
        if full and (len(questions) != 1 or len(tasks) != 1):
            errors.append(f"寫作測驗 prints exactly one guided-writing task (found {len(questions)} items)")
        for q in tasks:
            if q.get("options"):
                errors.append("寫作測驗 task must not print options")
            if q.get("score") not in (None, 6):
                errors.append("寫作測驗 is scored 1-6 級分; leave score unset or 6")
            if full:
                errors += writing_task_errors(q, answers.get(q.get("id")) or {})
        return errors
    if any(q.get("type") == "listening_choice" or q.get("audio") for q in questions):
        errors.append("英語聽力 is out of scope: the 英語 booklet is the reading booklet only")
    choice = [q for q in questions if q.get("type") in CHOICE_TYPES]
    constructed = [q for q in questions if q.get("type") in CONSTRUCTED_TYPES]
    other = [q for q in questions if q not in choice and q not in constructed]
    for q in other:
        errors.append(f"Q{q.get('number')}: type {q.get('type')!r} is not a 會考 {subject[2:]} item type")
    low, high = OFFICIAL_RANGES[subject]
    if full and not low <= len(choice) <= high:
        errors.append(f"{subject[2:]} prints {low}-{high} selected-response items (考試說明); found {len(choice)}")
    expected_constructed = CONSTRUCTED.get(subject, 0)
    if full and len(constructed) != expected_constructed:
        errors.append(f"{subject[2:]} prints {expected_constructed} 非選擇題; found {len(constructed)}")
    numbers = [q.get("number") for q in choice]
    if full and numbers != list(range(1, len(choice) + 1)):
        errors.append("selected-response items must be numbered 1..N in printed order")
    for q in choice:
        n = q.get("number")
        raw = tuple(str(o.get("label", "")) for o in q.get("options") or [] if isinstance(o, dict))
        labels = tuple(_label(o) for o in q.get("options") or [])
        if labels != LABELS:
            errors.append(f"Q{n}: 會考 single-choice items print exactly four options (A)-(D); got {labels}")
        elif raw != LABELS:
            errors.append(f"Q{n}: save option labels as plain A, B, C, D (the renderer prints the parentheses); got {raw}")
        key = re.sub(r"[()（）\s]", "", str((answers.get(q.get("id")) or {}).get("final_answer", "")))
        if key not in LABELS:
            errors.append(f"Q{n}: answer key {key!r} is not one of (A)-(D)")
        if q.get("score") not in (None, 1):
            errors.append(f"Q{n}: 會考 reports 答對題數, so each selected-response item counts once (score 1 or unset)")
    for q in constructed:
        if q.get("options"):
            errors.append(f"非選擇題 {q.get('number')}: must not print options")
        if not (answers.get(q.get("id")) or {}).get("rubric") and not (answers.get(q.get("id")) or {}).get("scoring_levels"):
            errors.append(f"非選擇題 {q.get('number')}: record the 0-3 級分 scoring rubric in the answer (rubric)")
    # Hosted 學測 papers keyed the longest option far more often than official papers (7-14%);
    # a test-wise student then needs no content knowledge. Keep it rare.
    longest = 0
    for q in choice:
        key = re.sub(r"[()（）\s]", "", str((answers.get(q.get("id")) or {}).get("final_answer", "")))
        lengths = {_label(o): len(re.sub(r"<[^>]+>|\s", "", str(o.get("text", "")))) for o in q.get("options") or []}
        if key in lengths and list(lengths.values()).count(max(lengths.values())) == 1 and lengths[key] == max(lengths.values()):
            longest += 1
    share = LONGEST_KEY_BY_SUBJECT.get(subject, LONGEST_KEY_SHARE)
    if full and choice and longest > max(2, round(share * len(choice))):
        errors.append(f"{longest} of {len(choice)} keys are the single longest option (at most "
                      f"{round(share * 100)}%): lengthen distractors so length never signals the answer")
    level = metadata.get("cap_difficulty_level", "會考")
    if level not in CAP_LEVELS:
        errors.append(f"metadata.cap_difficulty_level must be one of {'、'.join(CAP_LEVELS)} (the user's choice; default 會考)")
        level = "會考"
    for q in [*choice, *constructed]:
        n = q.get("number")
        codes = (q.get("item_spec") or {}).get("curriculum_codes") or []
        outside = [c for c in codes if not STAGE_IV_CODE.match(str(c).strip())]
        if outside:
            errors.append(f"Q{n}: curriculum codes {outside} are not 國中 第四學習階段 codes; no level may go beyond the "
                          "國中 curriculum")
        elif full and not codes:
            errors.append(f"Q{n}: item_spec.curriculum_codes must name the 108 課綱 國中 codes the item assesses")
        answer = answers.get(q.get("id")) or {}
        steps = [step for step in answer.get("reasoning") or [] if str(step).strip()]
        needed = max(MIN_STEPS[level], 3 if q in constructed else 0)
        if full and len(steps) < needed:
            errors.append(f"Q{n}: the explanation shows {len(steps)} reasoning step(s); a {level} paper needs at least "
                          f"{needed}: write how the answer follows from learned knowledge, step by step")
    situated = 0
    for q in [*choice, *constructed]:
        n = q.get("number")
        printed = " ".join([str(q.get("prompt") or ""), str(q.get("group_stimulus") or "")]
                           + [str(o.get("text") or "") for o in q.get("options") or [] if isinstance(o, dict)])
        if DISCLAIMERS.search(printed):
            errors.append(f"Q{n}: prints an invented-world disclaimer ({DISCLAIMERS.search(printed).group(0)}); "
                          "use a real, checkable situation instead")
        record = (q.get("item_spec") or {}).get("cap_competency")
        if not full:
            continue
        if not isinstance(record, dict):
            errors.append(f"Q{n}: item_spec.cap_competency is required (context_type, process, real_world_anchor, "
                          "evidence_link)")
            continue
        if record.get("context_type") not in CONTEXT_TYPES:
            errors.append(f"Q{n}: cap_competency.context_type must be one of {'、'.join(sorted(CONTEXT_TYPES))}")
        if record.get("process") not in PROCESSES:
            errors.append(f"Q{n}: cap_competency.process must be one of {'、'.join(sorted(PROCESSES))}")
        if not [k for k in record.get("prerequisite_knowledge") or [] if str(k).strip()]:
            errors.append(f"Q{n}: cap_competency.prerequisite_knowledge must list the learned 國中 concepts the derivation uses")
        for field in ("real_world_anchor", "evidence_link"):
            if not str(record.get(field) or "").strip():
                errors.append(f"Q{n}: cap_competency.{field} is empty (the real situation, and how the answer depends "
                              "on its evidence rather than on recall alone)")
        situated += record.get("context_type") in SITUATED_CONTEXTS
    items = len(choice) + len(constructed)
    if full and items and situated < SITUATED_SHARE[subject] * items:
        errors.append(f"only {situated} of {items} items are set in a real situation (生活情境／社會議題／科學探究／跨領域); "
                      f"{subject[2:]} needs at least {SITUATED_SHARE[subject]:.0%}, as official 會考 素養題 do")
    if full and items and subject in SITUATED_MAX and situated > SITUATED_MAX[subject] * items:
        errors.append(f"{situated} of {items} items are situated; official 會考{subject[2:]} 113-115 set about a third in a "
                      f"situation (at most {SITUATED_MAX[subject]:.0%} here) and ask the rest directly: computation, "
                      "geometric properties, judging two people's claims (context_type 學科知識)")
    groups: dict[str, list[int]] = {}
    for q in choice:
        if q.get("group_stimulus"):
            groups.setdefault(q["group_stimulus"], []).append(q.get("number"))
    for members in groups.values():
        if not 2 <= len(members) <= 7:
            errors.append(f"items {members}: a 會考 題組 holds 2-7 items")
        elif members != list(range(members[0], members[0] + len(members))):
            errors.append(f"items {members}: a 題組's items must be consecutive")
    from validate_cap_quality import validate_items
    errors.extend(validate_items(exam, full=full, asset_root=asset_root))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("exam", type=Path)
    parser.add_argument("--partial", action="store_true", help="skip whole-paper count checks")
    args = parser.parse_args()
    errors = validate_exam(json.loads(args.exam.read_text(encoding="utf-8-sig")), full=not args.partial)
    print(json.dumps({"status": "pass" if not errors else "fail", "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
