#!/usr/bin/env python3
"""Write the four mechanical paper reviews from executed checks, so authors spend their time on items.

structure_scope       the subject gate (form, counts, scope codes, item-quality floors) on the saved exam
difficulty_balance    validate_paper_difficulty_balance on the saved exam
template_composition  verify_fixed_template_pdf on both built booklets
answer_separation     the question booklet's text holds no key, solution step or solution heading

A review is `pass` only when its check executed and found nothing; otherwise `pending` with the
findings. The observations state what ran and what it measured, never an editorial judgement.
Item reviews (answers, difficulty, originality, visuals) and source_grounding stay with the reviewer.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

GATES = ("structure_scope", "difficulty_balance", "template_composition", "answer_separation")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pdfs(state: dict, root: Path) -> dict[str, Path]:
    out = {}
    for role, bundle in (state.get("pdfs") or {}).items():
        record = bundle.get("file") if isinstance(bundle, dict) else None
        if isinstance(record, dict) and (root / record.get("path", "")).is_file():
            out[role] = root / record["path"]
    return out


def structure_scope(exam: dict, root: Path, state: dict) -> tuple[bool, str]:
    from hosted_subject_gates import subject_gate_errors
    errors = subject_gate_errors(exam, root=root)
    questions = exam.get("questions") or []
    types = {}
    for q in questions:
        types[q.get("type")] = types.get(q.get("type"), 0) + 1
    codes = sum(1 for q in questions if (q.get("item_spec") or {}).get("curriculum_codes"))
    text = (f"executed hosted_subject_gates.subject_gate_errors on the saved exam: {len(questions)} items "
            f"{json.dumps(types, ensure_ascii=False)}, {codes} with curriculum codes; {len(errors)} findings")
    return not errors, text + ("" if not errors else ": " + " | ".join(errors[:12]))


def difficulty_balance(exam: dict, root: Path, state: dict) -> tuple[bool, str]:
    from validate_paper_difficulty_balance import validate
    result = validate(exam, root)
    text = (f"executed validate_paper_difficulty_balance: bands {json.dumps(result['count'], ensure_ascii=False)}, "
            f"estimated {result['estimated_minutes']:.1f} minutes; {len(result['errors'])} findings")
    return not result["errors"], text + ("" if not result["errors"] else ": " + " | ".join(result["errors"][:12]))


def template_composition(exam: dict, root: Path, state: dict) -> tuple[bool, str]:
    from verify_fixed_template_pdf import verify_pdf
    pdfs = _pdfs(state, root)
    if set(pdfs) != {"question", "solution"}:
        return False, "build both booklets first; no question/solution PDF is registered in this state"
    subject = exam["metadata"]["subject"]
    asset_dir = root / state["template_asset_dir"] if state.get("template_asset_dir") else None
    parts, ok = [], True
    for role, kind in (("question", "questions"), ("solution", "answers")):
        report = verify_pdf(pdfs[role], subject, kind, asset_dir)
        ok &= report["status"] == "pass-fixed-template"
        parts.append(f"{role} {pdfs[role].name} sha256 {_sha(pdfs[role])[:12]}: {report['status']}, "
                     f"{len(report['pages'])} pages" + (f", {report['errors'][:6]}" if report["errors"] else ""))
    return ok, "executed verify_fixed_template_pdf on both booklets: " + "; ".join(parts)


def answer_separation(exam: dict, root: Path, state: dict) -> tuple[bool, str]:
    import pymupdf
    pdfs = _pdfs(state, root)
    if "question" not in pdfs:
        return False, "build the question booklet first"
    with pymupdf.open(pdfs["question"]) as doc:
        text = re.sub(r"\s", "", "".join(page.get_text() for page in doc))
    findings = []
    for heading in ("答案：", "詳解", "參考答案", "解析："):
        if heading in text:
            findings.append(f"prints 「{heading}」")
    for answer in exam.get("answers") or []:
        for step in answer.get("reasoning") or []:
            probe = re.sub(r"\s", "", str(step))[:16]
            if len(probe) >= 12 and probe in text:
                findings.append(f"prints solution text of {answer.get('question_id')} 「{probe}」")
                break
    text_note = (f"executed a text search of {pdfs['question'].name} ({len(text)} characters) for solution headings and "
                 f"the first 16 characters of every saved solution step; {len(findings)} findings")
    return not findings, text_note + ("" if not findings else ": " + " | ".join(findings[:12]))


BANDS = (("very_hard", 0.30), ("hard", 0.50), ("medium", 0.70), ("easy", 0.85), ("very_easy", 1.01))


def difficulty_draft(exam: dict, root: Path) -> Path | None:
    """difficulty.draft.json for a 會考 paper: every row with the fields the final check reads, the anchor
    key its item type needs (objective / constructed-response), the official same-position 通過率 and
    the author's own estimates as a starting point. status stays pending: the reviewer re-solves each
    item with the answer covered, edits the estimates, writes observations and answer_recheck, then
    saves it as difficulty.json. A math author learned these fields one failed finalize at a time."""
    metadata = exam.get("metadata") or {}
    subject = metadata.get("subject")
    if not str(subject or "").startswith("會考"):
        return None
    try:
        from cap_plan import position_targets
        targets = position_targets(subject, metadata.get("cap_difficulty_level", "會考"))
    except (KeyError, OSError, ValueError):
        targets = {}
    from hosted_blind_review import packet as blind_packet
    exam_sha = _sha(root / "exam.json")
    packet = root / f"blind-packet-{exam_sha[:12]}.json"
    packet.write_text(json.dumps(blind_packet(exam, "single-context"), ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8", newline="\n")
    rows = []
    for q in exam.get("questions") or []:
        design = (q.get("item_spec") or {}).get("difficulty_design") or {}
        constructed = q.get("type") != "single_choice"
        p = design.get("estimated_p")
        target = targets.get(q.get("number")) if not constructed else None
        rows.append({
            "id": q.get("id"), "status": "pending", "observations": "",
            "estimated_p": p, "estimated_d": design.get("estimated_d"),
            "difficulty_band": next((b for b, edge in BANDS if type(p) in (int, float) and p < edge), None),
            "expected_minutes": design.get("expected_minutes"),
            "shortest_route": design.get("short_route") or "",
            "decisive_steps": [d for d in design.get("linked_decisions") or [] if d],
            "shortcut_search": "",
            "anchor_comparison": {"kind": "embedded-calibration",
                                  "key": "constructed-response" if constructed else "objective",
                                  "note": (f"official 113-115 position {q.get('number')}: 通過率 {target['official_p_113_115']}, "
                                           f"鑑別度 {target.get('official_d_113_115')}" if target else "")},
            "anchor": {"kind": "embedded-calibration", "key": "constructed-response" if constructed else "objective"},
            "answer_recheck": "", "unresolved": []})
    draft = {"draft_note": "pending until reviewed: re-solve each item with the answer covered, adjust the estimates, "
                           "fill observations, shortcut_search and answer_recheck, set status pass, remove this note, "
                           "save as difficulty.json",
             "exam_sha256": exam_sha, "status": "pending", "observations": "",
             "review_mode": "single-context", "independent_review": False, "review_reason": "",
             "author_context": "", "reviewer_context": "",
             "blind_packet": {"path": packet.name, "sha256": _sha(packet)},
             "items": rows}
    path = root / "difficulty.draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def auto_review(state_path, gates=GATES) -> dict:
    state_path = Path(state_path).resolve()
    root = state_path.parent
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    exam_path = root / "exam.json"
    exam = json.loads(exam_path.read_text(encoding="utf-8-sig"))
    exam_sha = _sha(exam_path)
    written = {}
    for gate in gates:
        if gate not in GATES:
            raise ValueError(f"auto-review covers {', '.join(GATES)} only; {gate} needs a reviewer")
        passed, observations = globals()[gate](exam, root, state)
        report = {"exam_sha256": exam_sha, "status": "pass" if passed else "pending", "observations": observations,
                  "produced_by": "hosted_auto_review (executed checks)"}
        (root / f"{gate}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written[gate] = report["status"]
    pending = [g for g, s in written.items() if s != "pass"]
    draft = difficulty_draft(exam, root)
    return {"status": "pending" if pending else "ok", "reviews": written,
            **({"difficulty_draft": draft.name} if draft else {}),
            "next_action": ("fix the findings in " + ", ".join(f"{g}.json" for g in pending) + ", then rerun auto-review"
                            if pending else "run checkpoint to register these reviews")}
