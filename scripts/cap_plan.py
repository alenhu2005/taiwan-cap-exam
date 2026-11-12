#!/usr/bin/env python3
"""會考 paper plans and item skeletons from the official 113-115 structure; never questions.

  plan   --subject 會考社會 --paper-id 20261111-01 [--year 116] [--level 高]  → plan.json for append_items.py --plan
  item   --subject 會考社會 --number 12 [--level 高]                          → one pending item and answer
  check  plan.json                                                           → plan problems before authoring
  expand --plan plan.json --compact items.json --run-dir RUN --output batch.json → full batch for append_items.py

Targets come from exam_packs/會考 (official 通過率 and 鑑別度 by position, 115 sections and 題組).
A level above 會考 lowers the target pass rate; it never widens the curriculum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
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
# Broad 國中 strands each slot is pointed at, drawn per paper_id so repeated papers cover different
# ground (a maintainer found repeated generations converging on the same topics and pictures).
FOCUS = {
    "歷史": ("七年級臺灣史・史前與原住民族", "七年級臺灣史・荷西與鄭氏", "七年級臺灣史・清帝國時期", "七年級臺灣史・日本統治時期",
             "七年級臺灣史・戰後臺灣", "八年級中國與東亞・先秦至隋唐", "八年級中國與東亞・宋元明清", "八年級中國與東亞・近代變局",
             "八年級中國與東亞・二十世紀", "九年級世界史・古代文明", "九年級世界史・中古至近代歐洲", "九年級世界史・帝國主義與世界大戰",
             "九年級世界史・冷戰與當代"),
    "地理": ("七年級臺灣・地形與氣候", "七年級臺灣・人口與產業", "七年級臺灣・區域與交通", "八年級中國與東亞・自然環境",
             "八年級中國與東亞・人口與產業", "九年級世界・東南亞與南亞", "九年級世界・西亞與非洲", "九年級世界・歐洲與俄羅斯",
             "九年級世界・美洲", "九年級世界・大洋洲與兩極", "地理技能・地圖與統計判讀"),
    "公民": ("七年級・個人、家庭與社群", "七年級・性別、文化與多元", "八年級・民主政治與政府", "八年級・法律與權利救濟",
             "八年級・刑法、民法與行政法", "九年級・經濟活動與市場", "九年級・貨幣、金融與政府經濟角色", "九年級・全球化與國際社會"),
    "會考自然": ("生物・細胞與生殖遺傳", "生物・生理與恆定", "生物・生態與演化", "理化・物質與化學反應", "理化・酸鹼與氧化還原",
                 "理化・力與運動", "理化・能量、熱與電磁", "理化・波動、光與聲", "地球科學・岩石、地形與板塊", "地球科學・天氣與氣候",
                 "地球科學・天文", "跨科・科學探究與資料判讀"),
    "會考數學": ("數與量", "代數與方程式", "函數與坐標", "平面幾何與證明", "空間與立體", "統計與機率", "數列與規律"),
    "會考國文": ("語文知識・字音字形與詞義", "語文知識・修辭與文法", "白話文閱讀", "文言文閱讀", "詩詞曲賞析", "應用文與圖表文本"),
    "會考英語": ("school life", "family and community", "health and sport", "science and technology", "environment",
                 "travel and culture", "work and money", "media and notices"),
}
TITLES = {"會考寫作測驗": "寫作測驗"}
# 會考數學 item forms, counted on 113-115 (M1111 wrote 22 of 25 as one textbook form: a story, then a
# number). Forms say what the student does, never which situation to use: the setting is the author's.
MATH_FORMS = {
    "直接作答：計算、化簡或圖形性質，不包情境": 9,
    "判斷兩人的看法或作法（甲、乙皆正確…）": 3,
    "推理大小、位置或必然性，不必算出數值": 3,
    "選出算式、關係式或圖形，而非數值": 2,
    "閱讀新資訊（表格、對話、規定、說明）後建立模型": 6,
    "判讀圖表資料後推論": 2,
}
MATH_OPENING_FORM = "直接作答：計算、化簡或圖形性質，不包情境"
MATH_GROUP_FORM = "閱讀新資訊（表格、對話、規定、說明）後建立模型"


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


def difficulty_label(p: float) -> str:
    """The official 會考 categories (易 p ≥ .70, 中 .40-.70, 難 < .40)."""
    return "易" if p >= 0.70 else "中" if p >= 0.40 else "難"


def discrimination_label(d: float) -> str:
    """Customary item-analysis grades (Ebel): ≥ .40 優良, .30-.39 良好, .20-.29 尚可, below 待改進."""
    return "優良" if d >= 0.40 else "良好" if d >= 0.30 else "尚可" if d >= 0.20 else "待改進"


def difficulty_note(item_spec: dict, reviewed: dict | None = None, *, constructed: bool = False) -> str:
    """Printed 「難易度：中（預估通過率 0.62）；鑑別度：優良（預估 0.45）」. Both are estimates made while
    writing and reviewing (the reviewed difficulty.json first), never results from examinees."""
    design = item_spec.get("difficulty_design") or {}
    p = (reviewed or {}).get("estimated_p", design.get("estimated_p"))
    d = (reviewed or {}).get("estimated_d", design.get("estimated_d"))
    parts = []
    if type(p) in (int, float) and 0 <= p <= 1:
        parts.append(f"難易度：{difficulty_label(p)}（預估{'得分率' if constructed else '通過率'} {p:.2f}）")
    if type(d) in (int, float) and -1 <= d <= 1:
        parts.append(f"鑑別度：{discrimination_label(d)}（預估 {d:.2f}）")
    return "；".join(parts)


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
        # D estimates anchor on the official items in this position, not on a fixed floor: official
        # hard positions run 0.13-0.45, and a fixed 0.40 floor only taught authors to inflate.
        out[n] = {"target_p": round(centre, 2), "official_p_113_115": [min(ps), max(ps)],
                  "official_d_113_115": [min(ds), max(ds)] if ds else None}
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


def math_forms(slots: list[dict], seed: str) -> dict:
    """{slot: form}: items 1-3 direct, the 題組 a modelling text, the rest a seeded shuffle."""
    import random
    rng = random.Random(hashlib.sha256(f"{seed}:forms".encode()).digest())
    left = dict(MATH_FORMS)
    out = {}
    for slot in slots:
        if slot["number"] <= 3:
            out[id(slot)] = MATH_OPENING_FORM
        elif slot.get("group"):
            out[id(slot)] = MATH_GROUP_FORM
        else:
            continue
        left[out[id(slot)]] -= 1
    rest = [s for s in slots if id(s) not in out]
    pool = [f for f, k in left.items() for _ in range(max(0, k))]
    pool += [MATH_OPENING_FORM] * (len(rest) - len(pool))
    rng.shuffle(pool)
    out.update({id(s): f for s, f in zip(rest, pool)})
    return [(s, out[id(s)]) for s in slots if id(s) in out]


def sections(subject: str) -> list[dict]:
    current = form(subject)["current_form"]
    titles = SECTION_TITLES.get(subject)
    found = current.get("sections_115") or []
    if not titles or len(found) < 2:
        return [{"id": "s1", "title": "", "instructions": []}]   # 自然, 寫作: no printed heading
    return [{"id": f"s{i + 1}", "title": titles[i].format(a=s["first"], b=s["last"], n=s["last"] - s["first"] + 1),
             "instructions": []} for i, s in enumerate(found[:2])]


def constructed_section(subject: str) -> str | None:
    """The section id of the 非選擇題 (數學 第二部分), or None."""
    found = form(subject)["current_form"].get("sections_115") or [] if subject != "會考寫作測驗" else []
    return "s2" if len(found) > 1 and "非選" in str(found[1].get("title")) else None


def constructed_labels(n: int) -> dict:
    """數學 非選擇題 print 「1.」「2.」 under 第二部分 but are saved after the choice items (26, 27),
    so their numbers never collide with choice items 1 and 2."""
    return {"number_display": f"{n}.", "answer_label": f"非選擇題第{n}題"}


def plan(subject: str, paper_id: str, year: str = "116", level: str = "會考", seed: str | None = None) -> dict:
    """A fresh random seed per plan unless one is given: two papers never share a topic draw,
    even with the same paper_id; the seed is saved so the same paper resumes with the same draw."""
    seed = seed or secrets.token_hex(8)
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
                                            "shared_reading_minutes": 0},
                "visual_contract": {}, "mixed_group_originality_records": [], "variety_seed": seed}
    slots = []
    if subject != "會考寫作測驗":
        targets = position_targets(subject, level)
        count = current["choice_items"]["reference_115"]
        groups = {n: g for g in current.get("groups_115") or [] for n in range(g[0], g[1] + 1)}
        # Reading a 題組's shared material once: about two minutes a group (a number, never null).
        metadata["difficulty_balance_plan"]["shared_reading_minutes"] = 2 * len(current.get("groups_115") or [])
        single = [n for n in range(1, count + 1) if n not in groups]
        schedule = dict(zip(single, domain_schedule(len(single), seed))) if subject == "會考社會" else {}
        secs = sections(subject)
        from cap_units import UNIT_RANGES, schedule as unit_schedule
        # 國文／英語／社會 print 題組 as their own second section; 數學's second section is the
        # 非選擇題, so its 題組 (23-25) stay in 第一部分.
        group_section = secs[1]["id"] if len(secs) > 1 and not constructed_section(subject) else secs[0]["id"]
        for n in range(1, count + 1):
            slot = {"number": n, "type": "single_choice",
                    "section_id": group_section if n in groups else secs[0]["id"],
                    "group": groups.get(n), **targets.get(n, {})}
            if n in schedule:
                slot["domain"] = schedule[n]
            slots.append(slot)
        if subject == "會考數學":
            for slot, suggested in math_forms(slots, seed):
                slot["suggested_form"] = suggested
        # Official unit coverage (cap_units.py): every paper starts inside the 113-115 ranges.
        units = unit_schedule(subject, slots, seed)
        for slot in slots:
            unit = units.get(slot["number"])
            if subject == "會考自然" and unit:
                slot["domain"] = unit
            elif unit:
                slot["unit"] = unit
            pool = FOCUS.get(slot.get("domain") or subject)
            if subject == "會考自然":
                pool = tuple(f for f in FOCUS["會考自然"] if f.startswith(slot.get("domain", "")) or f.startswith("跨科"))
            if pool and subject != "會考數學":
                rank = hashlib.sha256(f"{seed}:{slot['number']}".encode()).digest()[0]
                slot["suggested_focus"] = pool[rank % len(pool)]
        for n in range(1, current.get("constructed_items", 0) + 1):
            slots.append({"number": count + n, **constructed_labels(n), "type": "constructed_response",
                          "section_id": constructed_section(subject), "rubric": "0-3 級分"})
    if subject == "會考寫作測驗":
        from validate_cap_form import WRITING_NOTES, WRITING_RUBRIC
        metadata["writing_frame"] = {
            "opening": "請先閱讀以下資訊，並依據題意要求完成一篇文章。",
            "material_forms_113_115": ["一組生活中常見的文字樣本（標題、文案）", "一張圖片加一組可選的詞彙", "一段引導短文"],
            "task": "提出兩三個思考問題，再要求結合自己的經驗或見聞，寫下觀察、感受或想法；不給題目",
            "notes": list(WRITING_NOTES),
            "solution": f"審題與取材引導，並依 {'、'.join(WRITING_RUBRIC)}（格式與標點符號）四個向度說明各級分表現"}
    from cap_units import SCIENCE_SHARES, UNIT_RANGES
    coverage = ({u: list(r) for u, r in UNIT_RANGES[subject].items()} if subject in UNIT_RANGES else
                {d: [round(a, 2), round(b, 2)] for d, (a, b) in SCIENCE_SHARES.items()} if subject == "會考自然" else None)
    return {"metadata": metadata, "instructions": [], "sections": sections(subject),
            "planning_slots": slots,
            **({"unit_coverage": {"official_113_115": coverage,
                                  "note": "slots carry a unit (自然: domain) inside these ranges; swap units between slots "
                                          "freely, but the finished paper must stay inside them"}} if coverage else {}),
            "note": "append_items.py --plan keeps metadata, instructions and sections; planning_slots are guidance only. "
                    "Fill difficulty_balance_plan.target_counts before the first batch."}


def item(subject: str, number: int, level: str = "會考", kind: str = "single_choice") -> dict:
    slots = [s for s in plan(subject, "skeleton", level=level, seed="skeleton")["planning_slots"]
             if s["type"] == kind and (s["number"] == number or s.get("number_display") == f"{number}.")]
    if not slots:
        raise ValueError(f"{subject} has no {kind} slot {number}")
    slot = slots[0]
    choice = kind == "single_choice"
    steps = 3 if level in ("高", "極難") or not choice else 2
    printed = int(str(slot.get("number_display") or slot["number"]).rstrip("."))
    question = {"id": f"q{number}" if choice else f"c{printed}", "number": slot["number"], "section_id": slot["section_id"],
                "type": kind, "prompt": None, "group_stimulus": None, "visual_asset": None,
                **({"options": [{"label": c, "text": None} for c in "ABCD"]} if choice else constructed_labels(printed)),
                "item_spec": {
                    "curriculum_codes": [], "textbook_volumes": [],
                    **({"cap_unit": slot["unit"]} if slot.get("unit") else {}),
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
    return {"status": "pending-authoring", "subject": subject, "level": level, "slot": slot, "field_guide": FIELD_GUIDE,
            "question": question, "answer": answer,
            "rules": ["references/current-cap-form.md 品質標準 and 難度等級",
                      "cap_distractors: delete the key's row; each wrong option names its misconception and the real "
                      "neighbouring concept it borrows, never an absurd or absolute claim",
                      "hidden_concept: the term the student must infer; it may not appear in the stem, material or figure",
                      "混合考點: at least 20% of items join two domains (社會: cap_competency.domains, primary first) or two "
                      "curriculum strands, with a bridge saying why the answer needs both",
                      "figures carry evidence, never the conclusion; options alike in length and voice",
                      f"reasoning: at least {steps} steps from learned 國中 knowledge, then name every option (A)-(D) and why "
                      "each distractor fails; at least two linked_decisions",
                      "cap_distractors.*.expected_pick_rate: predicted share choosing each wrong option, at least 0.05",
                      "faster: write compact records (field_guide) and run `cap_plan.py expand`",
                      "textbook_volumes: the 國中 volume(s) the concepts are taught in, e.g. [\"第三冊\"] (第一冊=七上 … 第六冊=九下); "
                      "數學 may leave it empty, the code's grade is printed; the solution prints 課綱 and 可能出處"]}


FIELD_GUIDE = {
    "options": "four strings; or four image paths in compact `images` (options become {{asset:NAME}}, figures as options)",
    "key": "A | B | C | D",
    "steps": "list of strings: the derivation from learned 國中 knowledge, then why each other option is wrong, naming (A)-(D)",
    "codes": "108 課綱 第四學習階段 codes, e.g. a code ending -IV-n or 數學 N-8-1",
    "volumes": "list like [\"第三冊\"] (第一冊=七上 … 第六冊=九下); 數學 may omit",
    "context_type": "生活情境 | 社會議題 | 科學探究 | 跨領域 | 學科知識 | 文本閱讀",
    "process": "擷取訊息 | 統整解釋 | 推論 | 應用 | 評鑑",
    "anchor": "the real situation the item rests on", "evidence": "how the answer depends on the material's evidence",
    "prerequisites": "list of learned concepts the derivation uses", "hidden_concept": "the term the student must infer",
    "unit": "the slot's unit (數學／國文／英語, from the plan; swap with another slot if needed); 自然 uses domain",
    "domain": "自然: 生物 | 理化 | 地球科學 (the plan's slot domain by default)",
    "domains": "社會: list of 歷史/地理/公民, primary first", "bridge": "why the answer needs both concepts (混合考點)",
    "distractors": "{label: {misconception, peer_concept, pick (0-1, at least 0.05), ruled_out_by}} for each wrong option",
    "band": "簡單 | 中 | 中偏難 | 難", "est_p": "predicted 通過率 0-1", "est_d": "predicted 鑑別度 0-1",
    "decisions": "list of at least two linked decisions", "short_route": "the shortest correct route",
    "misconception": "the main trap", "bottleneck": "list of the hard points", "minutes": "expected solving minutes",
    "data_sources": "list of {url, retrieved_at} for every printed statistic",
    "figure": "{path, width_percent, visual_spec} for the item's own figure (web_image.py use prints visual_spec)",
    "material": "shared 題組 material (identical text for every item of the group)",
    "keep_order": "true keeps numeric options as written; otherwise expand sorts them ascending and relabels key and steps",
    "form": "數學: the slot's suggested_form says what the student does; the setting is yours",
}


def expand(plan_data: dict, compact: list[dict], run_dir: Path) -> dict:
    """Compact authoring records → the full batch append_items.py saves (ids, sections, labels, hashes)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_paper_difficulty_balance import content_hash
    subject = plan_data["metadata"]["subject"]
    slots = {(s["number"], s["type"]): s for s in plan_data.get("planning_slots") or []}
    choice_count = sum(1 for s in plan_data.get("planning_slots") or [] if s.get("type") == "single_choice")
    sha = lambda p: hashlib.sha256((run_dir / p).read_bytes()).hexdigest()
    questions, answers, leaders, reordered = [], [], {}, {}
    for row in compact:
        kind = "constructed_response" if row.get("constructed") else "single_choice"
        number = row["number"]
        if kind == "constructed_response" and number <= choice_count:
            number = choice_count + number   # 非選擇題 1 → saved as 26 (printed 「1.」)
        slot = slots.get((number, kind), {})
        printed = number - choice_count if kind == "constructed_response" else number
        qid = row.get("id") or (f"q{number}" if kind == "single_choice" else f"c{printed}")
        q = {"id": qid, "number": number, "type": kind,
             "section_id": row.get("section") or slot.get("section_id") or "s1", "prompt": row["stem"]}
        if row.get("material"):
            q["group_stimulus"] = row["material"]
        if kind == "constructed_response":
            q.update(constructed_labels(printed))
        elif row.get("images"):
            q["inline_assets"] = {f"{qid}{c}": {"path": p, "width_pt": row.get("image_width_pt", 120), "sha256": sha(p)}
                                  for c, p in zip("ABCD", row["images"])}
            q["options"] = [{"label": c, "text": "{{asset:" + f"{qid}{c}" + "}}"} for c in "ABCD"]
        else:
            q["options"] = [{"label": c, "text": t} for c, t in zip("ABCD", row["options"])]
            if not row.get("keep_order"):
                row = sort_numeric_options(row, q)
        if row.get("figure"):
            figure = dict(row["figure"])
            figure["sha256"] = sha(figure["path"])
            q["visual_asset"] = figure
        competency = {"context_type": row.get("context_type"), "process": row.get("process"),
                      "real_world_anchor": row.get("anchor"), "evidence_link": row.get("evidence"),
                      "prerequisite_knowledge": row.get("prerequisites") or [], "hidden_concept": row.get("hidden_concept"),
                      "bridge": row.get("bridge")}
        domains = row.get("domains") or ([row["domain"]] if row.get("domain") else []) or \
            ([slot["domain"]] if slot.get("domain") else [])
        if domains:
            competency.update(domain=domains[0], domains=domains)
        band = row.get("band")
        spec = {"curriculum_codes": row.get("codes") or [], "textbook_volumes": row.get("volumes") or [],
                **({"cap_unit": row.get("unit") or slot.get("unit")} if row.get("unit") or slot.get("unit") else {}),
                "cap_competency": competency, "difficulty": {"label": band},
                "difficulty_design": {"band": band, "basis": row.get("basis") or "113-115 官方同題位通過率",
                                      "confidence": row.get("confidence") or "中", "short_route": row.get("short_route"),
                                      "misconception": row.get("misconception"), "linked_decisions": row.get("decisions") or [],
                                      "bottleneck": row.get("bottleneck") or [], "expected_minutes": row.get("minutes"),
                                      "estimated_p": row.get("est_p"), "estimated_d": row.get("est_d"),
                                      **({"shortcut_status": "reviewed-no-direct-collapse"} if band in ("中偏難", "難") else {})}}
        if row.get("data_sources"):
            spec["data_sources"] = row["data_sources"]
        if kind == "single_choice":
            spec["cap_distractors"] = {c: {"misconception": d.get("misconception"), "peer_concept": d.get("peer_concept"),
                                           "expected_pick_rate": d.get("pick"), "ruled_out_by": d.get("ruled_out_by")}
                                       for c, d in (row.get("distractors") or {}).items() if c != row.get("key")}
        if row.get("material"):
            leader = leaders.setdefault(row["material"], qid)
            if leader != qid:
                spec["inherits_audit_from"] = leader
        spec.update(row.get("item_spec_extra") or {})
        q["item_spec"] = spec
        spec["difficulty_design"]["content_sha256"] = content_hash(q)
        questions.append(q)
        if row.get("sorted_options"):
            reordered[qid] = row["sorted_options"]
        answer = {"question_id": qid, "final_answer": row.get("key") or row.get("answer"), "difficulty_label": band,
                  "reasoning": row.get("steps") or []}
        if kind == "constructed_response":
            answer["rubric"] = row.get("rubric")
        answers.append(answer)
    batch = {"questions": questions, "answers": answers}
    if reordered:
        batch["options_reordered"] = reordered   # reported by the CLI, removed before writing
    return batch


LABEL_REF = re.compile(r"([（(]\s*)([ABCD])(\s*[)）])|(選項\s*)([ABCD])|([ABCD])(\s*選項)")


def sort_numeric_options(row: dict, question: dict) -> dict:
    """Plain numeric options in ascending order, as official 113-115 print them; the key, the distractor
    records and every (A)-(D) mention in the steps follow their option."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_cap_quality import numeric_values
    values = numeric_values([o["text"] for o in question["options"]])
    if not values or values == sorted(values) or values == sorted(values, reverse=True):
        return row
    order = sorted(range(4), key=lambda i: values[i])
    mapping = {"ABCD"[old]: "ABCD"[new] for new, old in enumerate(order)}
    question["options"] = [{"label": "ABCD"[new], "text": question["options"][old]["text"]} for new, old in enumerate(order)]
    relabel = lambda text: LABEL_REF.sub(lambda m: "".join(
        mapping[g] if g in mapping else g or "" for g in m.groups()), str(text))
    row = dict(row)
    if row.get("key") in mapping:
        row["key"] = mapping[row["key"]]
    row["distractors"] = {mapping.get(k, k): v for k, v in (row.get("distractors") or {}).items()}
    row["steps"] = [relabel(step) for step in row.get("steps") or []]
    row["sorted_options"] = mapping
    return row


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
    p.add_argument("--seed", help="reuse a saved variety_seed (resuming the same paper); omit for a new draw")
    i = sub.add_parser("item"); i.add_argument("--subject", required=True, choices=SUBJECTS)
    i.add_argument("--number", type=int, required=True); i.add_argument("--level", default="會考", choices=LEVELS)
    i.add_argument("--constructed", action="store_true", help="數學 非選擇題 slot")
    c = sub.add_parser("check"); c.add_argument("plan", type=Path)
    e = sub.add_parser("expand", help="compact authoring records → full append_items batch")
    e.add_argument("--plan", type=Path, required=True); e.add_argument("--compact", type=Path, required=True)
    e.add_argument("--run-dir", type=Path, required=True); e.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "plan":
        result = plan(args.subject, args.paper_id, args.year, args.level, args.seed)
        if args.output:
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {"status": "plan-written", "output": str(args.output), "check": check(result)}
    elif args.command == "item":
        result = item(args.subject, args.number, args.level, "constructed_response" if args.constructed else "single_choice")
    elif args.command == "expand":
        batch = expand(json.loads(args.plan.read_text(encoding="utf-8")),
                       json.loads(args.compact.read_text(encoding="utf-8")), args.run_dir.resolve())
        reordered = batch.pop("options_reordered", None)
        args.output.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
        if reordered:
            batch["options_reordered"] = reordered
        result = {"status": "batch-written", "output": str(args.output), "items": len(batch["questions"]),
                  **({"options_reordered": batch["options_reordered"]} if batch.get("options_reordered") else {}),
                  "next": f"python scripts/append_items.py --run-dir {args.run_dir} --batch {args.output}"}
    else:
        errors = check(json.loads(args.plan.read_text(encoding="utf-8")))
        result = {"status": "pass" if not errors else "fix-before-authoring", "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
