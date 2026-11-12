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

from cap_units import SINGLE_DECISION_UNITS, unit_errors

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
# 英語 options are words of natural length (bow/smell, it/like this): official 113-115 have 9 of 43
# items a year over the limit, so 英語 takes the official share; the others keep the 社會 floor.
SPREAD_SHARE_BY_SUBJECT = {"會考英語": 0.21}
# Extreme wording is a 社會／自然 distractor defect; 國文 options paraphrase literary texts (「毫無」
# 「從不」 occur in official 113 國文 options) and 英語 options are English.
EXTREME_SUBJECTS = {"會考社會", "會考自然", "會考數學"}
# 數學 items judging two people's claims or methods (115 第 14、20、22 題; 113 第 9、24 題; 114 第 12、18 題);
# 自然 items judging a prediction, a claim or a classification (113: 6, 114: 1, 115: 4).
JUDGE_MIN = {"會考數學": 2, "會考自然": 1}
# 自然 experiment items (variables, procedure, results): 113-115 4-9 a year plus the 題組 experiments.
INQUIRY_MIN = {"會考自然": 4}
# Negative stems (「何者錯誤」「最不可能」「無法」「NOT」), 113-115 at most: 國文 5, 自然 3, 數學 1.
NEGATIVE_STEM = re.compile(r"不可能|無法|錯誤|不正確|最不|不包含|不是|不適合|不合理|\bNOT\b|\bEXCEPT\b")
NEGATIVE_MAX = {"會考國文": 5, "會考自然": 3, "會考數學": 1, "會考英語": 3}
# 英語 題組 questions (113-115 by hand): 細節 5-6, 推論與字義 5-7, 主旨／目的／比較 3-7, 應用 2-3 a year.
ENGLISH_GROUP_PROCESS_MIN = {"擷取訊息": 3, "推論": 4, "統整解釋": 3, "應用": 1}
ABSOLUTE_SHARE = 0.05   # official up to 9%; target above official
TRANSLATION_SHARE = 0.6   # 社會: items whose target concept the student must infer
INTEGRATED_SHARE = 0.20  # items joining concepts across domains (社會) or curriculum strands (others)
SINGLE_STEP_SHARE = 0.20  # items answerable from one decision (cap116a: 「單一知識點直球對決」)
MIN_PICK_RATE = 0.05      # a distractor nobody chooses does not discriminate
MAX_RUN, MIN_SWITCHES = 7, 10
# Settings of the worked examples in references/current-cap-form.md and of reviewed AI papers: they
# illustrate a technique, and a paper that reuses them repeats other papers instead of inventing.
EXAMPLE_SETTINGS = re.compile(r"坑頭|坑尾|咖啡(?:果|農場)|剝除果皮|柏林圍牆|聖索菲亞|尼羅河.{0,6}夜|朗多尼亞|魚骨狀|五腳基|"
                              r"斯巴達.{0,4}棄嬰|普魯塔克|牙刷主義|床蝨|臭蟲|北極.{0,4}航線|宏都拉斯.{0,4}白蝦|"
                              r"天災減產導致供給|立賣契人|竹塹社")
# cap116a took all 11 photographs from the bundled 59-photo library although the preflight found
# web images reachable; every paper then repeats the same pictures. With the web reachable,
# most photographs must be newly found (scripts/web_image.py); the library is the fallback.
# Official 113-115 booklets (scripts/build_cap_pack.py measurements, 2026-11): 甲乙丙丁 combination
# items per paper, items whose four options are figures (lower bounds: options printed as images
# only), and option length in characters (median, share over 20).
COMBO = re.compile(r"[甲乙丙丁戊己].*[甲乙丙丁戊己]")
COMBO_MAX = {"會考社會": 3, "會考自然": 5, "會考數學": 3, "會考國文": 1, "會考英語": 1}
IMAGE_OPTION_MIN = {"會考社會": 2, "會考自然": 3}
OPTION_LENGTH = {"會考社會": (15, 0.12), "會考自然": (14, 0.27), "會考國文": (19, 0.25)}   # median cap, share >20
# 社會 prints real data, so every printed statistic needs its source. Elsewhere official items use
# hypothetical numbers (「某國政府公布…」, an experiment's readings, a shop's prices): only a sentence that
# claims real data (a year, 根據／調查／統計／公布, a named survey) and names no 「某」 needs a source.
CLAIM = re.compile(r"(?:19|20)\d{2}\s*年|根據|依據|公布|統計|調查|報告|資料顯示|研究指出|官方|according to|survey|"
                   r"statistic|reported|census", re.I)
STATISTIC = re.compile(r"\d[\d,.]*\s*(?:%|％|萬|億|人|公噸|噸|元|美元|度|公里|公頃|戶|件|次|倍|毫米|mm|℃)")
OVERLAP_MIN, OVERLAP_PHRASES = 6, 2   # shared distinctive runs, in at least two separate phrases
FINGERPRINTS = Path(__file__).resolve().parents[1] / "exam_packs" / "會考" / "metadata" / "official-item-fingerprints.json"
FRESH_PHOTO_SHARE = 1.0   # maintainer: every photograph newly found when the web is reachable
PHOTO_KINDS = {"photo", "archival_image", "satellite_image", "aerial_photo", "artifact_photo"}


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


def official_overlaps(text: str) -> list[tuple[str, int, int, int]]:
    """(subject, year, number, shared) for official items sharing OVERLAP_MIN distinctive wording runs."""
    if not FINGERPRINTS.is_file():
        return []
    import hashlib
    import json
    index = getattr(official_overlaps, "_index", None)
    if index is None:
        index = {}
        for item in json.loads(FINGERPRINTS.read_text(encoding="utf-8"))["items"]:
            for g in item["grams"]:
                index[g] = (item["subject"], item["year"], item["number"])
        official_overlaps._index = index
    # A single shared term (「日本統治時期」, 「法定代理人」) is curriculum vocabulary, not a rewrite: count
    # shared runs AND the separate phrases they form; a rewrite shares several phrases.
    plain_text = re.sub(r"\s", "", text)
    positions: dict[tuple, list[int]] = {}
    for i, g in enumerate(re.findall(r"(?=([\u4e00-\u9fff]{4}))", plain_text)):
        h = int(hashlib.sha1(g.encode("utf-8")).hexdigest()[:8], 16)
        if h in index:
            positions.setdefault(index[h], []).append(i)
    out = []
    for key, where in positions.items():
        where = sorted(set(where))
        phrases = 1 + sum(1 for a, b in zip(where, where[1:]) if b - a > 1)
        if len(where) >= OVERLAP_MIN and phrases >= OVERLAP_PHRASES:
            out.append((*key, len(where)))
    return out


def spec_sources(question: dict) -> list[dict]:
    spec = question.get("item_spec") or {}
    rows = spec.get("data_sources") or []
    return [r for r in rows if isinstance(r, dict)]


def real_data(subject: str | None, text: str) -> bool:
    """Printed numbers presented as real-world data (社會: any printed statistic)."""
    if subject == "會考社會":
        return bool(STATISTIC.search(text))
    return any(STATISTIC.search(s) and CLAIM.search(s) and "某" not in s for s in re.split(r"[。！？!?\n]", text))


# Running mean of estimated_p while writing, against the plan's own targets for the same positions:
# items are saved in any order, and the first easy positions alone sit above the paper's band
# (a math author had to save hard items early to pass). Within this tolerance of the targets.
RUNNING_TOLERANCE = 0.08


def running_mean_errors(exam: dict, subject: str | None, numbered: list[tuple[int, float]]) -> list[str]:
    if len(numbered) < 5:
        return []
    from hosted_blind_review import CAP_MEAN_P
    if subject not in CAP_MEAN_P:
        return []
    from cap_plan import position_targets
    level = (exam.get("metadata") or {}).get("cap_difficulty_level", "會考")
    level = level if level in ("會考", "中", "高", "極難") else "會考"
    targets = position_targets(subject, level)
    pairs = [(p, targets[n]["target_p"]) for n, p in numbered if n in targets]
    if len(pairs) < 5:
        return []
    mean = sum(p for p, _ in pairs) / len(pairs)
    expected = sum(t for _, t in pairs) / len(pairs)
    if abs(mean - expected) <= RUNNING_TOLERANCE:
        return []
    return [f"running mean of estimated_p over the {len(pairs)} saved items is {mean:.2f}; the {level} targets for "
            f"those positions average {expected:.2f} (±{RUNNING_TOLERANCE}): adjust the next items now, not after the "
            "paper is written"]


def validate_items(exam: dict, *, full: bool = True, asset_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    metadata = exam.get("metadata") or {}
    subject = metadata.get("subject")
    answers = {a.get("question_id"): a for a in exam.get("answers") or [] if isinstance(a, dict)}
    choice = [q for q in exam.get("questions") or [] if isinstance(q, dict) and q.get("type") == "single_choice"]
    spread_items = absolute_items = translation = single_step = integrated = combos = image_options = judges = 0
    numbered_estimates: list[tuple[int, float]] = []
    option_lengths: list[int] = []
    estimates: list[float] = []
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
        raw_texts = [str(o.get("text") or "") for o in q.get("options") or [] if isinstance(o, dict)]
        if raw_texts and all(re.fullmatch(r"\s*\{\{asset:[^{}]+\}\}\s*", t) for t in raw_texts):
            image_options += 1
        elif all(COMBO.search(t) for t in options.values()):
            combos += 1
        option_lengths += [len(t) for t in options.values() if t]
        printed_all = str(q.get("group_stimulus") or "") + str(q.get("prompt") or "") + " ".join(raw_texts)
        for official in official_overlaps(printed_all + figure):
            errors.append(f"Q{n}: shares {official[3]} distinctive wording runs with official {official[1]} "
                          f"{official[0][2:]} item {official[2]}: compare the two: if yours retells that item's situation, write a new one")
        if real_data(subject, printed_all + "。" + figure):
            sources = [s for s in spec_sources(q) if str(s.get("url") or "").startswith("http") and s.get("retrieved_at")]
            if full and not sources:
                errors.append(f"Q{n}: prints real-world data; item_spec.data_sources must list each figure's source "
                              "{url, retrieved_at}: look the numbers up, never write them from memory"
                              + ("" if subject == "會考社會" else " (or make it hypothetical, as official items do: "
                                 "「某國」「某商店」 and no year or survey named)"))
        estimate = ((q.get("item_spec") or {}).get("difficulty_design") or {}).get("estimated_p")
        if type(estimate) in (int, float):
            estimates.append(float(estimate))
            numbered_estimates.append((n, float(estimate)))
        elif full:
            errors.append(f"Q{n}: item_spec.difficulty_design.estimated_p (predicted 通過率) is required while writing, "
                          "so the paper's difficulty is steered before review")
        if subject == "會考社會" and leak(options[key], others, material):
            errors.append(f"Q{n}: the stem or material repeats the key's wording; official 會考社會 113-115 never do: "
                          "make the student infer it")
        for label, text in options.items():
            if subject in EXTREME_SUBJECTS and EXTREME.search(text):
                errors.append(f"Q{n}: option ({label}) uses extreme wording 「{EXTREME.search(text).group(0)}」 (0 of 496 "
                              "official options): write a plausible distractor from a real neighbouring concept")
        absolute = [label for label, text in options.items() if ABSOLUTE.search(text)]
        absolute_items += bool(absolute) and key not in absolute
        lengths = [len(t) for t in options.values() if t]
        if lengths and len(options[key]) >= 4 and max(lengths) / max(1, min(lengths)) > SPREAD_LIMIT:
            spread_items += 1
        setting = EXAMPLE_SETTINGS.search(str(q.get("group_stimulus") or "") + str(q.get("prompt") or ""))
        if setting:
            errors.append(f"Q{n}: reuses the setting 「{setting.group(0)}」 of a worked example or a reviewed paper; examples "
                          "show a technique only: invent a new situation for this paper")
        if LEAD_IN.search(str(q.get("group_stimulus") or "") + str(q.get("prompt") or "")):
            errors.append(f"Q{n}: do not type the 題組 lead-in (「閱讀下列選文，回答…」); the renderer prints it once")
        if subject in NON_MATH and COUNTING.search(str(q.get("prompt") or "")):
            errors.append(f"Q{n}: asks the student to count things on a figure; ask what the evidence shows instead")
        if subject in {"會考社會", "會考國文", "會考英語"} and ARITHMETIC.search(str(q.get("prompt") or "")):
            errors.append(f"Q{n}: is an arithmetic exercise; {subject[2:]} items assess the subject's concepts")
        spec = q.get("item_spec") or {}
        record = spec.get("cap_competency") if isinstance(spec.get("cap_competency"), dict) else {}
        judges += record.get("process") == "評鑑"
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
            if spec.get("cap_unit") not in SINGLE_DECISION_UNITS:   # 英語 字彙／文法, 國文 語文知識: one decision
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
    errors += running_mean_errors(exam, subject, numbered_estimates)
    errors += unit_errors(subject, choice, full=full)
    if not full or not choice:
        return errors
    if combos > COMBO_MAX.get(subject, 1):
        errors.append(f"{combos} items are 甲乙丙丁 combinations (official 113-115 at most {COMBO_MAX.get(subject, 1)} a paper): "
                      "the format, not the thinking, makes them hard; write single-answer reasoning items")
    if image_options < IMAGE_OPTION_MIN.get(subject, 0):
        errors.append(f"{image_options} items use figures as options (official every year at least "
                      f"{IMAGE_OPTION_MIN[subject]}): add items whose four options are maps, charts or diagrams "
                      "({{asset:NAME}} as the whole option text)")
    if subject in OPTION_LENGTH and option_lengths:
        import statistics
        cap, share = OPTION_LENGTH[subject]
        median = statistics.median(option_lengths)
        long_share = sum(n > 20 for n in option_lengths) / len(option_lengths)
        if median > cap or long_share > share:
            errors.append(f"options run long (median {median:g} characters, {long_share:.0%} over 20; official at most "
                          f"{cap - 2} and {share:.0%}): put the difficulty in the material and stem, keep options short")
    if asset_root is not None and (Path(asset_root) / "preflight.json").is_file():
        import json
        try:
            reachable = (json.loads((Path(asset_root) / "preflight.json").read_text(encoding="utf-8"))
                         .get("image_sources") or {}).get("web_images") == "reachable"
        except ValueError:
            reachable = False
        modes = [((q.get("visual_asset") or {}).get("visual_spec") or {}).get("generation_mode")
                 for q in choice if (((q.get("visual_asset") or {}).get("visual_spec") or {}).get("kind")) in PHOTO_KINDS]
        assets = {}
        for q in choice:
            asset = q.get("visual_asset") or {}
            spec_ = asset.get("visual_spec") or {}
            if spec_.get("kind") in PHOTO_KINDS:
                assets[asset.get("sha256") or asset.get("path")] = spec_.get("generation_mode")
        fresh = sum(mode == "web_source" for mode in assets.values())
        if reachable and assets and fresh < FRESH_PHOTO_SHARE * len(assets):
            errors.append(f"only {fresh} of {len(assets)} photographs are newly found (web_source); the web is reachable, so "
                          "every photograph must be: search with `python scripts/web_image.py search \"…\"` and "
                          "use `web_image.py use`; the bundled photo library is the fallback when the web is unreachable")
    errors += subject_habit_errors(exam)
    errors += option_order_errors(exam)
    errors += curve_errors(exam)
    errors += math_form_errors(exam, asset_root=asset_root)
    if judges < JUDGE_MIN.get(subject, 0):
        errors.append(f"{judges} items ask the student to judge others' claims or methods (cap_competency.process 評鑑); "
                      f"official 會考數學 prints 2-3 a year (「甲、乙兩人的看法」「兩人的作法」): write at least {JUDGE_MIN[subject]}")
    if spread_items > max(2, SPREAD_SHARE_BY_SUBJECT.get(subject, SPREAD_SHARE) * len(choice)):
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


# ---- 數學 and option-form rules from the M1111 reviews (2026-11), measured on 113-115 ----

# Plain numeric options print in order (official 113-115: every such item, mostly ascending); M1111
# left 18 of 25 unsorted. Fractions, radicals and expressions are ordered by form and are not checked.
NUMERIC_OPTION = re.compile(r"^(-?\d+(?:\.\d+)?)([^\d\s/√×÷^+=<>{}]{0,6})$")


def numeric_values(texts: list[str]) -> list[float] | None:
    values, units = [], set()
    for text in texts:
        raw = re.sub(r"<[^>]+>|\s|,", "", str(text or "")).replace("−", "-")
        match = NUMERIC_OPTION.match(raw)
        if not match:
            return None
        values.append(float(match.group(1)))
        units.add(match.group(2))
    return values if len(units) == 1 else None


# Textbook and workbook archetypes: a paper made of them reads as 參考書, not 會考 (M1111: a ladder
# sliding down a wall, fencing against a wall, auditorium rows, a bouncing ball, a die net, a
# spinner, straws in hexagons, a folded rectangle). Official 113-115 use at most one a paper.
MATH_ARCHETYPES = {
    "梯子沿牆下滑": r"梯子?.{0,40}牆.{0,40}滑|梯.{0,10}滑.{0,30}牆",
    "靠牆圍籬求面積": r"靠.{0,8}牆.{0,40}圍(?:籬|欄)|圍(?:籬|欄).{0,40}靠.{0,6}牆",
    "每排座位等差": r"每一?排.{0,16}(?:多|少)\s*\d*\s*(?:個|張)?座位",
    "彈力球反彈": r"彈力球|反彈.{0,12}高度",
    "雞兔同籠": r"雞.{0,12}兔|兔.{0,12}雞",
    "骰子展開圖": r"骰子.{0,30}展開|展開圖.{0,30}骰子",
    "轉盤機率": r"轉盤",
    "吸管火柴排圖形": r"(?:吸管|火柴|牙籤).{0,40}(?:圖形|排成|拼成|黏出)",
    "沿對角線摺紙": r"沿.{0,8}對角線.{0,12}(?:摺|折)",
    "二分球三分球": r"(?:二|2)\s*分球.{0,30}(?:三|3)\s*分球",
    "色紙磁磚貼滿": r"(?:磁磚|色紙|地磚).{0,40}(?:貼滿|鋪滿)",
    "紙張疊放厚度": r"(?:影印紙|紙張).{0,30}厚度",
    "放入物體水位上升": r"(?:放入|沉入|直立放入).{0,40}水(?:面|位|深).{0,16}(?:上升|高度|多少)",
}
ARCHETYPE_MAX = 2
# Integer right-triangle families (3-4-5 …): M1111 built item 20, the 23-25 題組 and 非選擇題 2 on 6-8-10.
TRIPLES = ((3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (9, 40, 41))
TRIPLE_ITEMS_MAX = 2   # official 113: 2 (第 4、22 題), 114: 0, 115: 1
GEOMETRIC_UNITS = {"平面幾何", "相似形與三角形三心", "圓", "立體與空間", "坐標與函數"}
# 數學 options that are statements, relations, expressions, positions or judgements, not a bare number:
# official 113-115 12-14 of 25 a paper; M1111 about 4.
FORM_OPTION_MIN = {"會考數學": 0.40}
CURVE_TOLERANCE = 0.10


def triple_families(text: str) -> set[tuple]:
    """Families whose three sides all print, or two legs at a multiple of two or more (6 and 8, 10 and 24)."""
    numbers = {int(n) for n in re.findall(r"(?<![\d.])(\d{1,3})(?![\d.])", text)}
    found = set()
    for family in TRIPLES:
        for k in range(1, 41):
            sides = [k * side for side in family]
            if all(side in numbers for side in sides) or (k >= 2 and sides[0] in numbers and sides[1] in numbers):
                found.add(family)
                break
    return found


def math_form_errors(exam: dict, *, asset_root: Path | None = None) -> list[str]:
    """Whole-paper 會考數學 checks: opening items, option forms, archetypes, repeated triangles."""
    subject = (exam.get("metadata") or {}).get("subject")
    questions = [q for q in exam.get("questions") or [] if isinstance(q, dict)]
    choice = [q for q in questions if q.get("type") == "single_choice"]
    errors: list[str] = []
    if subject != "會考數學" or not choice:
        return errors
    for q in choice:
        if q.get("number") in (1, 2, 3):
            record = (q.get("item_spec") or {}).get("cap_competency") or {}
            if record.get("context_type") not in (None, "學科知識"):
                errors.append(f"Q{q.get('number')}: 113-115 open with three direct items (a computation, a figure's "
                              "property): no story in items 1-3 (context_type 學科知識)")
    formed = sum(numeric_values([o.get("text") for o in q.get("options") or [] if isinstance(o, dict)]) is None
                 and not all(re.fullmatch(r"\s*-?−?\d+(?:\.\d+)?\s*", re.sub(r"\{\{frac:[^}]*\}\}|\d+/\d+", "1", str(o.get("text") or "")))
                             for o in q.get("options") or [] if isinstance(o, dict))
                 for q in choice)
    if formed < FORM_OPTION_MIN[subject] * len(choice):
        errors.append(f"only {formed} of {len(choice)} items have options other than a bare number; official 會考數學 "
                      f"113-115 print 12-14 a paper (at least {FORM_OPTION_MIN[subject]:.0%}): ask for a relation, a position, "
                      "an expression, a statement or a judgement where the reasoning, not the arithmetic, is the point")
    hits: dict[str, list] = {}
    families: dict[tuple, list] = {}
    for q in questions:
        text = " ".join([str(q.get("group_stimulus") or ""), str(q.get("prompt") or "")]
                        + [str(o.get("text") or "") for o in q.get("options") or [] if isinstance(o, dict)])
        label = q.get("number_display") or q.get("number")
        for name, pattern in MATH_ARCHETYPES.items():
            if re.search(pattern, re.sub(r"\s", "", text)):
                hits.setdefault(name, []).append(label)
        # Geometry and coordinate items and the 非選擇題 only (a probability item's 3, 4 and 5 are not a
        # triangle); a 題組 counts once.
        unit = (q.get("item_spec") or {}).get("cap_unit")
        if q.get("type") != "single_choice" or unit in GEOMETRIC_UNITS:
            stem = " ".join([str(q.get("group_stimulus") or ""), str(q.get("prompt") or "")])
            owner = f"題組({str(q.get('group_stimulus'))[:6]})" if q.get("group_stimulus") else label
            for family in triple_families(stem + " " + figure_text(q, asset_root)):
                if owner not in families.setdefault(family, []):
                    families[family].append(owner)
    if sum(len(v) for v in hits.values()) > ARCHETYPE_MAX:
        listed = "；".join(f"{k}（{', '.join(map(str, v))}）" for k, v in hits.items())
        errors.append(f"{sum(len(v) for v in hits.values())} items rebuild a textbook exercise ({listed}); official papers "
                      f"use at most one, here at most {ARCHETYPE_MAX}: keep the concept, invent the situation and the question")
    for family, labels in families.items():
        if len(set(map(str, labels))) > TRIPLE_ITEMS_MAX:
            errors.append(f"items {', '.join(map(str, labels))} all rest on the {'-'.join(map(str, family))} right-triangle "
                          f"family; vary the numbers so no family appears in more than {TRIPLE_ITEMS_MAX} items")
    return errors


def option_order_errors(exam: dict) -> list[str]:
    errors = []
    for q in exam.get("questions") or []:
        if not isinstance(q, dict) or q.get("type") != "single_choice":
            continue
        values = numeric_values([o.get("text") for o in q.get("options") or [] if isinstance(o, dict)])
        if values and values != sorted(values) and values != sorted(values, reverse=True):
            errors.append(f"Q{q.get('number')}: numeric options print in order (official 113-115 always do, mostly "
                          f"ascending); got {', '.join(f'{v:g}' for v in values)}: reorder them and move the key "
                          "(cap_plan.py expand sorts them for you)")
    return errors


def curve_errors(exam: dict) -> list[str]:
    """Estimated 通過率 by thirds of the paper against the official position targets: 會考 papers open easy
    and close hard (M1111 put a die net and a one-step circumcentre at 19-20)."""
    from hosted_blind_review import CAP_MEAN_P
    from cap_plan import position_targets
    metadata = exam.get("metadata") or {}
    subject = metadata.get("subject")
    if subject not in CAP_MEAN_P:
        return []
    level = metadata.get("cap_difficulty_level", "會考")
    targets = position_targets(subject, level if level in ("會考", "中", "高", "極難") else "會考")
    rows = []
    for q in exam.get("questions") or []:
        estimate = ((q.get("item_spec") or {}).get("difficulty_design") or {}).get("estimated_p")
        if q.get("type") == "single_choice" and type(estimate) in (int, float) and q.get("number") in targets:
            rows.append((q["number"], float(estimate), targets[q["number"]]["target_p"]))
    if len(rows) < 9:
        return []
    rows.sort()
    size = len(rows) // 3
    errors = []
    for name, part in (("first", rows[:size]), ("middle", rows[size:-size]), ("last", rows[-size:])):
        estimated = sum(r[1] for r in part) / len(part)
        target = sum(r[2] for r in part) / len(part)
        if abs(estimated - target) > CURVE_TOLERANCE:
            errors.append(f"the {name} third of the paper (items {part[0][0]}-{part[-1][0]}) is estimated at 通過率 "
                          f"{estimated:.2f}; the official positions average {target:.2f} (±{CURVE_TOLERANCE}): "
                          + ("move harder items later or make these more direct" if estimated < target else
                             "this part needs harder items: official 會考 builds from easy openings to the hardest items "
                             "before the 題組"))
    return errors


def subject_habit_errors(exam: dict) -> list[str]:
    """Official 113-115 habits per subject (exam_packs/會考/metadata/official-item-analysis.json)."""
    subject = (exam.get("metadata") or {}).get("subject")
    choice = [q for q in exam.get("questions") or [] if isinstance(q, dict) and q.get("type") == "single_choice"]
    errors: list[str] = []
    if not choice:
        return errors
    negative = [q.get("number") for q in choice if NEGATIVE_STEM.search(re.sub(r"\s", " ", str(q.get("prompt") or ""))[-60:])]
    if subject in NEGATIVE_MAX and len(negative) > NEGATIVE_MAX[subject]:
        errors.append(f"items {negative} ask in the negative (「何者錯誤」「最不可能」); official {subject[2:]} 113-115 at most "
                      f"{NEGATIVE_MAX[subject]} a paper: ask what follows, not what fails")
    competency = lambda q: ((q.get("item_spec") or {}).get("cap_competency") or {})
    if subject in INQUIRY_MIN:
        inquiry = sum(competency(q).get("context_type") == "科學探究" for q in choice)
        if inquiry < INQUIRY_MIN[subject]:
            errors.append(f"{inquiry} items are experiments or investigations (context_type 科學探究); official 自然 has 4-9 a "
                          "year besides the 題組: variables, a procedure, results to interpret")
    if subject == "會考英語":
        groups = [q for q in choice if q.get("group_stimulus") and (q.get("item_spec") or {}).get("cap_unit") != "克漏字"]
        if len(groups) >= 10:
            for process, least in ENGLISH_GROUP_PROCESS_MIN.items():
                count = sum(competency(q).get("process") == process for q in groups)
                if count < least:
                    errors.append(f"{count} 題組 questions ask for {process}; official 英語 113-115 ask at least {least} "
                                  "(details, inference and word meaning in context, main idea or purpose, applying the text)")
        singles = [q for q in choice if not q.get("group_stimulus")]
        if singles and not any(q.get("visual_asset") for q in singles):
            errors.append("英語 113-115 open the 單題 with a picture item (「Look at the picture.」): give one 單題 a picture")
    return errors
