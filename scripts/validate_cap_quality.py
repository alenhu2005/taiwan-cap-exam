#!/usr/bin/env python3
"""Item-quality floors for 會考 papers, measured on the official 113-115 booklets.

Each rule answers a defect found when hosted papers were compared with 115 會考 社會
(maintainer review, 2026-11): figures and captions that print the answer, absurd
「一律／歸零／宣告獨立」 distractors, items solved by counting shaded bars or by
long division, domains in three solid blocks, stems that name the concept they ask
for, and 題組 lead-ins typed into the material. Thresholds sit at the official level:

* the key's wording inside the stem, material or figure: 0 of 113 measured 社會 items
  share a 6-character run with the key that the distractors do not;
* extreme wording (歸零、終身、廢除、宣告獨立、全體、片面、徹底…): 0 of 496 official options;
* absolute words only in distractors: 2-4 items a year (at most 9%);
* option length: longest/shortest median 1.00-1.08, 90% of items at most 1.75;
* 社會 standalone items 1-43 (115): domains in short runs, longest about 5, about 18 switches.

Structural only: passing here never certifies quality; reviewers still read every item.
"""
from __future__ import annotations

import re
from pathlib import Path

LABELS = ("A", "B", "C", "D")
EXTREME = re.compile(r"歸零|終身|廢除|宣告獨立|全體|片面|毫無|從不|徹底|立即消失|永久禁止|全面禁止|完全消失|無限")
ABSOLUTE = re.compile(r"完全|一律|全面|全部|所有|絕對|永遠|必定|一定|只要|只有|只能|只會|只保障|僅|任何|必須|禁止|強制"
                      r"|無權|不受[^，。]{0,8}約束|連[^，。]{1,6}也|就算")
LEAD_IN = re.compile(r"(?:閱讀|請閱讀).{0,10}回答.{0,6}\d+\s*[～~至-]\s*\d+|\d+\s*[-～]\s*\d+\s*(?:題)?為題組")
COUNTING = re.compile(r"共有幾|有幾個|有幾項|幾座|幾根|多少個|多少項")
ARITHMETIC = re.compile(r"四捨五入|平均每[^，。]{0,12}約|約為多少|約多少(?:人|元|公里|公尺)")
DOMAINS = {"會考社會": ("歷史", "地理", "公民"), "會考自然": ("生物", "理化", "地球科學")}
NON_MATH = {"會考國文", "會考英語", "會考社會", "會考自然"}
LEAK_RUN = 6          # characters of the key's wording
LEAK_MARGIN = 4       # longer than any distractor's shared run by this much
SPREAD_LIMIT = 2.0    # longest/shortest option length
SPREAD_SHARE = 0.10
ABSOLUTE_SHARE = 0.05   # official up to 9%; target above official
TRANSLATION_SHARE = 0.6   # 社會: items whose target concept the student must infer
INTEGRATED_SHARE = 0.20  # items joining concepts across domains (社會) or curriculum strands (others)
SINGLE_STEP_SHARE = 0.20  # items answerable from one decision (cap116a: 「單一知識點直球對決」)
MIN_PICK_RATE = 0.05      # a distractor nobody chooses does not discriminate
MAX_RUN, MIN_SWITCHES = 7, 10


def plain(value) -> str:
    text = value.get("rich", "") if isinstance(value, dict) else str(value or "")
    return re.sub(r"<[^>]+>|[\s　，。、；：「」『』（）()《》〈〉？！?!,.:;\"'-]", "", text)


def longest_run(a: str, b: str) -> int:
    best, prev = 0, [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def figure_text(question: dict, asset_root: Path | None) -> str:
    """Words a student can read on the item's figure: its printed labels and caption."""
    asset = question.get("visual_asset")
    if not isinstance(asset, dict):
        return ""
    from validate_visual_item_contract import _asset_label_text, _label_strings
    spec = asset.get("visual_spec") if isinstance(asset.get("visual_spec"), dict) else {}
    parts = _label_strings(spec.get("semantic_data")) + [str(asset.get(k) or "") for k in ("caption", "title")]
    if asset_root is not None and asset.get("path"):
        parts += _asset_label_text(Path(asset_root) / str(asset["path"]))
    return plain(" ".join(parts))


def leak(key_text: str, others: list[str], source: str) -> int:
    """Length of the key's run in `source` when it beats every distractor's by LEAK_MARGIN."""
    if len(key_text) < LEAK_RUN or not source:
        return 0
    run = longest_run(key_text, source)
    rival = max((longest_run(o, source) for o in others), default=0)
    return run if run >= LEAK_RUN and run - rival >= LEAK_MARGIN else 0


def validate_items(exam: dict, *, full: bool = True, asset_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    metadata = exam.get("metadata") or {}
    subject = metadata.get("subject")
    answers = {a.get("question_id"): a for a in exam.get("answers") or [] if isinstance(a, dict)}
    choice = [q for q in exam.get("questions") or [] if isinstance(q, dict) and q.get("type") == "single_choice"]
    spread_items = absolute_items = translation = single_step = integrated = 0
    sequence: list[str] = []
    for q in choice:
        n = q.get("number")
        options = {re.sub(r"[()（）\s]", "", str(o.get("label", ""))): plain(o.get("text"))
                   for o in q.get("options") or [] if isinstance(o, dict)}
        key = re.sub(r"[()（）\s]", "", str((answers.get(q.get("id")) or {}).get("final_answer", "")))
        if set(options) != set(LABELS) or key not in options:
            continue   # validate_cap_form reports the shape
        others = [v for k, v in options.items() if k != key]
        material = plain(q.get("group_stimulus")) + plain(q.get("prompt"))
        figure = figure_text(q, asset_root)
        run = leak(options[key], others, figure)
        if run:
            errors.append(f"Q{n}: the figure or its caption prints the answer ({run} characters of option ({key})): "
                          "a figure carries evidence to interpret, never the conclusion")
        if subject == "會考社會" and leak(options[key], others, material):
            errors.append(f"Q{n}: the stem or material repeats the key's wording; official 會考社會 113-115 never do: "
                          "make the student infer it")
        for label, text in options.items():
            if EXTREME.search(text):
                errors.append(f"Q{n}: option ({label}) uses extreme wording 「{EXTREME.search(text).group(0)}」 (0 of 496 "
                              "official options): write a plausible distractor from a real neighbouring concept")
        absolute = [label for label, text in options.items() if ABSOLUTE.search(text)]
        absolute_items += bool(absolute) and key not in absolute
        lengths = [len(t) for t in options.values() if t]
        if lengths and len(options[key]) >= 4 and max(lengths) / max(1, min(lengths)) > SPREAD_LIMIT:
            spread_items += 1
        if LEAD_IN.search(str(q.get("group_stimulus") or "") + str(q.get("prompt") or "")):
            errors.append(f"Q{n}: do not type the 題組 lead-in (「閱讀下列選文，回答…」); the renderer prints it once")
        if subject in NON_MATH and COUNTING.search(str(q.get("prompt") or "")):
            errors.append(f"Q{n}: asks the student to count things on a figure; ask what the evidence shows instead")
        if subject in {"會考社會", "會考國文", "會考英語"} and ARITHMETIC.search(str(q.get("prompt") or "")):
            errors.append(f"Q{n}: is an arithmetic exercise; {subject[2:]} items assess the subject's concepts")
        spec = q.get("item_spec") or {}
        record = spec.get("cap_competency") if isinstance(spec.get("cap_competency"), dict) else {}
        # 混合考點: one item joining concepts from two domains (社會) or two curriculum strands, with
        # the bridge that makes both necessary (115 第 46-48 題: 媒體識讀 + 統計表判讀).
        domains = [d for d in (record.get("domains") or [record.get("domain") or spec.get("domain")]) if d]
        strands = {re.match(r"^[^-]+", str(c)).group(0) for c in spec.get("curriculum_codes") or [] if str(c).strip()}
        joined = len(set(domains)) >= 2 if subject == "會考社會" else len(strands) >= 2
        if joined and not str(record.get("bridge") or "").strip():
            errors.append(f"Q{n}: an item joining several concepts records cap_competency.bridge: why the answer "
                          "needs both, not two facts side by side")
        integrated += joined and bool(str(record.get("bridge") or "").strip())
        hidden = str(record.get("hidden_concept") or "").strip()
        if hidden:
            translation += 1
            printed = material + figure + "".join(others)
            if plain(hidden) and plain(hidden) in printed:
                errors.append(f"Q{n}: the concept the student must infer (「{hidden}」) is printed in the stem, material, "
                              "figure or distractors")
        if full:
            distractors = spec.get("cap_distractors")
            if not isinstance(distractors, dict):
                errors.append(f"Q{n}: item_spec.cap_distractors is required: for each wrong option, the misconception it "
                              "catches and the real neighbouring concept it borrows")
            else:
                for label in LABELS:
                    if label == key:
                        continue
                    row = distractors.get(label) if isinstance(distractors.get(label), dict) else {}
                    if not str(row.get("misconception") or "").strip() or not str(row.get("peer_concept") or "").strip():
                        errors.append(f"Q{n}: cap_distractors.{label} needs misconception and peer_concept")
                    # cap116a Q37 keyed 「放棄的打工收入」 beside 「活動費用加上放棄的收入」, defensible under a
                    # broader definition: name the textbook rule or evidence that makes each distractor wrong.
                    if not str(row.get("ruled_out_by") or "").strip():
                        errors.append(f"Q{n}: cap_distractors.{label}.ruled_out_by: the 國中 textbook definition or the "
                                      "material's evidence that makes this option definitely wrong; if none exists, rewrite it")
                    pick = row.get("expected_pick_rate")
                    if type(pick) not in (int, float) or not 0 <= pick <= 1:
                        errors.append(f"Q{n}: cap_distractors.{label}.expected_pick_rate (predicted share of examinees "
                                      "choosing it, 0-1) is required")
                    elif pick < MIN_PICK_RATE:
                        errors.append(f"Q{n}: option ({label}) is predicted to draw {pick:.0%} of examinees: a distractor "
                                      "no one chooses does not discriminate; borrow a concept students really confuse")
            decisions = (spec.get("difficulty_design") or {}).get("linked_decisions") or []
            single_step += len([d for d in decisions if d]) < 2
            # Every option is argued in the explanation, so a defensible second answer surfaces in review
            # (cap116a Q37 listed total cost and forgone income side by side).
            reasoning = " ".join(str(step) for step in (answers.get(q.get("id")) or {}).get("reasoning") or [])
            unnamed = [label for label in LABELS
                       if not re.search(rf"[（(]\s*{label}\s*[)）]|選項\s*{label}|{label}\s*選項", reasoning)]
            if unnamed:
                errors.append(f"Q{n}: the explanation never addresses option(s) {', '.join(unnamed)}: show why the key "
                              "follows and why each distractor fails, so no second answer is defensible")
        if full and subject != "會考數學":
            volumes = [str(v) for v in spec.get("textbook_volumes") or [] if str(v).strip()]
            if not volumes or not all(re.match(r"^第[一二三四五六]冊", v) for v in volumes):
                errors.append(f"Q{n}: item_spec.textbook_volumes lists the 國中 volume(s) teaching these concepts "
                              "(第一冊=七上 … 第六冊=九下); the solution prints it as 可能出處")
        if subject in DOMAINS and not q.get("group_stimulus"):
            domain = (record.get("domains") or [None])[0] or record.get("domain") or spec.get("domain")
            if domain not in DOMAINS[subject]:
                if full:
                    errors.append(f"Q{n}: cap_competency.domain must be one of {'、'.join(DOMAINS[subject])}")
            else:
                sequence.append(domain)
    if not full or not choice:
        return errors
    if spread_items > max(2, SPREAD_SHARE * len(choice)):
        errors.append(f"{spread_items} items have one option over {SPREAD_LIMIT:g} times as long as another (official 90% "
                      f"at most 1.75): keep the four options alike in length, voice and structure")
    if absolute_items > max(2, ABSOLUTE_SHARE * len(choice)):
        errors.append(f"{absolute_items} items put absolute words (一律、只有、完全…) only in distractors (official 2-4 a "
                      "year): a test-wise student eliminates them without the concept")
    if integrated < INTEGRATED_SHARE * len(choice):
        what = "歷史／地理／公民 (cap_competency.domains)" if subject == "會考社會" else "two curriculum strands (curriculum_codes)"
        errors.append(f"only {integrated} of {len(choice)} items join concepts across {what} with a bridge; at least "
                      f"{INTEGRATED_SHARE:.0%}: write 混合考點 items whose answer needs both concepts")
    if single_step > max(2, SINGLE_STEP_SHARE * len(choice)):
        errors.append(f"{single_step} items need fewer than two linked decisions (difficulty_design.linked_decisions); "
                      f"at most {SINGLE_STEP_SHARE:.0%}: official items link evidence to a concept and then apply it")
    if subject == "會考社會":
        if translation < TRANSLATION_SHARE * len(choice):
            errors.append(f"only {translation} of {len(choice)} items make the student infer the concept "
                          f"(cap_competency.hidden_concept); 會考社會 needs at least {TRANSLATION_SHARE:.0%}: give sources, "
                          "maps, data or letters, not the textbook term")
    if subject == "會考社會" and len(sequence) >= 20:
        runs, longest, switches = 1, 1, 0
        for before, after in zip(sequence, sequence[1:]):
            runs = runs + 1 if before == after else 1
            switches += before != after
            longest = max(longest, runs)
        if longest > MAX_RUN or switches < MIN_SWITCHES:
            errors.append(f"單題 domains run in blocks (longest run {longest}, {switches} switches): 115 會考社會 alternates "
                          f"歷史／地理／公民 in short runs; keep runs at most {MAX_RUN} and at least {MIN_SWITCHES} switches")
        for domain in DOMAINS[subject]:
            share = sequence.count(domain) / len(sequence)
            if not 0.25 <= share <= 0.42:
                errors.append(f"{domain} holds {share:.0%} of the 單題; keep each of 歷史／地理／公民 between 25% and 42%")
    return errors
