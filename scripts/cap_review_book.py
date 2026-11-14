#!/usr/bin/env python3
"""One review record per item, written batch by batch, compiled into the five 會考 review reports.

A 54-item 會考社會 run wrote answers.json, difficulty.json, originality.json, visuals.json and
source_grounding.json (270 KB) after the whole paper, then regenerated drafts and blind packets
four times as items changed. Here the reviewer fills `review-book.json` while each batch is fresh:

  python scripts/run_hosted_workflow.py review-book --state RUN/run-state.json      sync rows with saved items
  python scripts/run_hosted_workflow.py compile-reviews --state RUN/run-state.json  write the five reports

`append_items.py` syncs the book after every 會考 batch. A row is keyed by the item's content hash:
an unchanged item keeps its review through any layout change; an edited item's row returns to
pending with the earlier review kept under `previous`. Compiling writes nothing until every row
is reviewed, and it never writes a pass the reviewer did not record.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BOOK = "review-book.json"
BANDS = (("very_hard", 0.30), ("hard", 0.50), ("medium", 0.70), ("easy", 0.85), ("very_easy", 1.01))
SECTIONS = ("answer_check", "originality", "visual", "difficulty")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def item_hash(question: dict, answer: dict) -> str:
    """The printed item and its key and solution: what a review vouches for."""
    printed = {k: question.get(k) for k in ("prompt", "group_stimulus", "options", "visual_asset", "inline_assets", "type")}
    solved = {k: answer.get(k) for k in ("final_answer", "reasoning", "rubric")}
    return hashlib.sha256(json.dumps([printed, solved], ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _row(question: dict, answer: dict, target: dict | None) -> dict:
    design = (question.get("item_spec") or {}).get("difficulty_design") or {}
    constructed = question.get("type") != "single_choice"
    p = design.get("estimated_p")
    has_figure = bool(question.get("visual_asset") or question.get("inline_assets"))
    anchor = {"kind": "embedded-calibration", "key": "constructed-response" if constructed else "objective"}
    return {
        "id": question.get("id"), "content_sha256": item_hash(question, answer),
        "answer_check": {"status": "pending", "observations": "",
                         "how": "cover the key, solve again, compare; say why each distractor is definitely wrong"},
        "originality": {"status": "pending", "observations": "",
                        "how": "differs from official items, textbook exercises and this paper's other items"},
        "visual": ({"status": "pending", "observations": "", "how": "the evidence a student reads on the figure"}
                   if has_figure else {"status": "not_applicable", "observations": "此題無圖"}),
        "difficulty": {
            "status": "pending", "observations": "",
            "estimated_p": p, "estimated_d": design.get("estimated_d"),
            "difficulty_band": next((b for b, edge in BANDS if type(p) in (int, float) and p < edge), None),
            "expected_minutes": design.get("expected_minutes"),
            "shortest_route": design.get("short_route") or "",
            "decisive_steps": [d for d in design.get("linked_decisions") or [] if d],
            "shortcut_search": "", "answer_recheck": "",
            "anchor_comparison": {**anchor, "note": (f"official 113-115 position {question.get('number')}: 通過率 "
                                                     f"{target['official_p_113_115']}, 鑑別度 {target.get('official_d_113_115')}"
                                                     if target else "")},
            "anchor": anchor, "unresolved": []},
        "sources": [s.get("url") for s in (question.get("item_spec") or {}).get("data_sources") or [] if isinstance(s, dict)],
    }


def sync(root: Path, exam: dict) -> dict:
    """Add rows for new items, reset rows of edited items, keep reviewed unchanged ones."""
    root = Path(root)
    path = root / BOOK
    book = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "purpose": "per-item review records; compile-reviews writes the five reports from them",
        "paper": {"difficulty_review": {"review_mode": "single-context", "independent_review": False,
                                        "review_reason": "", "author_context": "", "reviewer_context": ""},
                  "originality_scope": "no-history-available",
                  "source_grounding": {"status": "pending", "observations": "",
                                       "how": "where each material and number comes from and how it was checked"}},
        "items": []}
    metadata = exam.get("metadata") or {}
    try:
        from cap_plan import position_targets
        targets = position_targets(metadata.get("subject"), metadata.get("cap_difficulty_level", "會考"))
    except Exception:  # noqa: BLE001 - writing subjects and unknown keys have no position targets
        targets = {}
    answers = {a.get("question_id"): a for a in exam.get("answers") or []}
    rows = {r.get("id"): r for r in book.get("items") or []}
    out, added, reset = [], [], []
    for q in exam.get("questions") or []:
        answer = answers.get(q.get("id")) or {}
        fresh = _row(q, answer, targets.get(q.get("number")) if q.get("type") == "single_choice" else None)
        old = rows.get(q.get("id"))
        if old is None:
            out.append(fresh)
            added.append(q.get("id"))
        elif old.get("content_sha256") != fresh["content_sha256"]:
            fresh["previous"] = {k: old.get(k) for k in SECTIONS}
            out.append(fresh)
            reset.append(q.get("id"))
        else:
            old.setdefault("sources", fresh["sources"])
            out.append(old)
    book["items"] = out
    path.write_text(json.dumps(book, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pending = [r["id"] for r in out if any((r.get(s) or {}).get("status") not in ("pass", "not_applicable") for s in SECTIONS)]
    return {"book": BOOK, "added": added, "reset_after_edit": reset, "pending": pending}


def _missing(section: dict, name: str, rid: str) -> list[str]:
    allowed = ("pass", "not_applicable") if name == "visual" else ("pass",)
    problems = []
    if section.get("status") not in allowed:
        problems.append(f"{rid}.{name}.status")
    if not str(section.get("observations") or "").strip():
        problems.append(f"{rid}.{name}.observations")
    if name == "difficulty":
        for field in ("estimated_p", "estimated_d", "shortest_route", "decisive_steps", "shortcut_search", "answer_recheck"):
            if section.get(field) in (None, "", []):
                problems.append(f"{rid}.difficulty.{field}")
    return problems


def compile_reports(root: Path, exam: dict, exam_path: Path) -> dict:
    """Write answers / originality / visuals / difficulty / source_grounding from a complete book."""
    root = Path(root)
    book_path = root / BOOK
    if not book_path.is_file():
        return {"status": "pending", "errors": ["no review-book.json yet: run review-book first"]}
    book = json.loads(book_path.read_text(encoding="utf-8"))
    answers = {a.get("question_id"): a for a in exam.get("answers") or []}
    rows = {r.get("id"): r for r in book.get("items") or []}
    problems = []
    for q in exam.get("questions") or []:
        row = rows.get(q.get("id"))
        if row is None:
            problems.append(f"{q.get('id')}: no row (run review-book)")
            continue
        if row.get("content_sha256") != item_hash(q, answers.get(q.get("id")) or {}):
            problems.append(f"{q.get('id')}: edited since its review (run review-book, then review it again)")
            continue
        for name in SECTIONS:
            problems += _missing(row.get(name) or {}, name, q.get("id"))
    paper = book.get("paper") or {}
    review = paper.get("difficulty_review") or {}
    for field in ("review_reason", "author_context", "reviewer_context"):
        if review.get("review_mode", "single-context") == "single-context" and not str(review.get(field) or "").strip():
            problems.append(f"paper.difficulty_review.{field}")
    grounding = paper.get("source_grounding") or {}
    if grounding.get("status") != "pass" or not str(grounding.get("observations") or "").strip():
        problems.append("paper.source_grounding (status pass and observations)")
    if problems:
        return {"status": "pending", "errors": problems[:40], "error_count": len(problems)}
    exam_sha = _sha(exam_path)
    order = [rows[q.get("id")] for q in exam.get("questions") or []]
    count = len(order)
    def report(name, items, **extra):
        body = {"exam_sha256": exam_sha, "status": "pass",
                "observations": f"compiled from {BOOK}: {count} items reviewed one by one, each record bound to the "
                                f"item's content hash", **extra, "items": items}
        (root / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    report("answers", [{"id": r["id"], "status": r["answer_check"]["status"], "observations": r["answer_check"]["observations"]}
                       for r in order])
    report("originality", [{"id": r["id"], "status": r["originality"]["status"], "observations": r["originality"]["observations"]}
                           for r in order], comparison_scope=paper.get("originality_scope", "no-history-available"), history=[])
    report("visuals", [{"id": r["id"], "status": r["visual"]["status"], "observations": r["visual"]["observations"]}
                       for r in order])
    from hosted_blind_review import packet
    mode = review.get("review_mode", "single-context")
    blind = root / f"blind-packet-{exam_sha[:12]}.json"
    blind.write_text(json.dumps(packet(exam, mode), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    difficulty_rows = []
    for r in order:
        d = {k: v for k, v in r["difficulty"].items() if k not in ("how",)}
        difficulty_rows.append({"id": r["id"], **d})
    report("difficulty", difficulty_rows, review_mode=mode, independent_review=review.get("independent_review", False),
           review_reason=review.get("review_reason"), author_context=review.get("author_context"),
           reviewer_context=review.get("reviewer_context"), blind_packet={"path": blind.name, "sha256": _sha(blind)})
    sources = (root / "source_grounding.json")
    sources.write_text(json.dumps({"exam_sha256": exam_sha, "status": "pass", "observations": grounding["observations"],
                                   "sources": sorted({u for r in order for u in r.get("sources") or [] if u})},
                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"status": "compiled", "reports": ["answers.json", "originality.json", "visuals.json", "difficulty.json",
                                              "source_grounding.json"],
            "next": "run checkpoint to register them, then auto-review for the mechanical reports"}
