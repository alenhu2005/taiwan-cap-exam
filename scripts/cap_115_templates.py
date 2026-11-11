#!/usr/bin/env python3
"""Deterministic 115-form 國中教育會考 booklet furniture.

Layout-only material for the five 會考 booklets this Skill produces: the subject
cover, the inner page (a centred page number, plus 「請翻頁繼續作答」 on the even
pages that precede the last question page) and the 數學 reference-formula page.
It never creates questions. 英語 is the reading booklet only; the listening
section is out of scope.

Measured on the official 115 booklets (cap.rcpet.edu.tw, 2026-05). Those print on
595.28 x 822.05 pt; these templates print on A4 so they share the composer and
body renderer with 學測. Positions keep the official distance from the top edge
(cover, body) or from the bottom edge (page number, page-turn cue).
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "exam_packs" / "會考" / "templates" / "115"
EXAM = "會考"
PAGE_W, PAGE_H = 595.28, 841.89
OFFICIAL_PAGE_H = 822.05
BOTTOM_SHIFT = PAGE_H - OFFICIAL_PAGE_H   # footer furniture keeps its distance from the bottom
TURN_CUE = "請翻頁繼續作答"

# Template keys are prefixed so 會考 社會/自然 never resolve to the 學測 records.
SUBJECT_ORDER = ("國文", "英語", "數學", "社會", "自然", "寫作測驗")
SUBJECTS: dict[str, dict[str, Any]] = {
    "國文": {"slug": "cap-chinese", "title": "國文科試題本", "sheet": "答案卡", "items": 42, "pages": 14,
            "duration": 70, "clock": ("13：50", "15：00"), "footer_pt": 12.0, "footer_top": 762.5},
    "英語": {"slug": "cap-english", "title": "英語科閱讀試題本", "sheet": "答案卡", "items": 43, "pages": 14,
            "duration": 60, "clock": ("10：30", "11：30"), "footer_pt": 12.0, "footer_top": 767.0},
    "數學": {"slug": "cap-math", "title": "數學科試題本", "sheet": "答案卷", "items": 25, "pages": 13,
            "duration": 80, "clock": ("10：30", "11：50"), "footer_pt": 13.0, "footer_top": 762.3,
            "formula": True, "constructed": 2},
    "社會": {"slug": "cap-social", "title": "社會科試題本", "sheet": "答案卡", "items": 54, "pages": 14,
            "duration": 70, "clock": ("08：30", "09：40"), "footer_pt": 12.0, "footer_top": 769.2},
    "自然": {"slug": "cap-science", "title": "自然科試題本", "sheet": "答案卡", "items": 50, "pages": 14,
            "duration": 70, "clock": ("08：30", "09：40"), "footer_pt": 12.0, "footer_top": 762.5},
    "寫作測驗": {"slug": "cap-writing", "title": "寫作測驗試題本", "sheet": "答案卷", "items": 1, "pages": 2,
              "duration": 50, "clock": ("15：50", "16：40"), "footer_pt": None, "footer_top": None},
}
# Body box measured on every 115 booklet: text from x 65.2 to 533.3, from 53 pt below the
# top edge to just above the page number.
BODY_BOX = (65.2, 53.0, 533.4, 776.0)
WRITING_BODY_BOX = (65.2, 53.0, 533.4, 800.0)


def template_key(subject: str) -> str:
    return EXAM + subject


def subject_config(subject: str) -> dict[str, Any]:
    name = subject[len(EXAM):] if subject.startswith(EXAM) else subject
    try:
        return SUBJECTS[name]
    except KeyError as exc:
        raise ValueError(f"不支援的115會考模板科目：{subject}") from exc


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _times(text: str) -> str:
    parts = re.split(r"(&[a-z#0-9]+;|<[^>]+>)", text)
    return "".join(part if part.startswith(("&", "<")) else re.sub(
        r"[A-Za-z0-9][A-Za-z0-9 .:-]*[A-Za-z0-9]|[A-Za-z0-9]", lambda m: f'<span class="tnr">{m.group(0)}</span>', part)
        for part in parts)


# A count the composer fills in (pages, items). Empty, fixed-width, so the cover's
# other glyphs never move; the map builder locates it from the text around it.
def _slot(name: str) -> str:
    return f'<span class="slot slot-{name}"></span>'


def _bubble(letter: str, kind: str = "") -> str:
    return f'<span class="bubble {kind}">{_e(letter) if kind not in {"full", "double"} else ""}</span>'


def _marking_example(sheet: str) -> str:
    def row(cells, note):
        return f'<p class="mark-row">{"".join(cells)}<span class="mark-note">—{note}</span></p>'
    return (f'<p>請依照題意從四個選項中選出一個正確或最佳的答案，並用 <b class="tnr">2B</b> 鉛筆</p>'
            f'<p>在{sheet}上相應的位置畫記，請務必將選項塗黑、塗滿。如果需要修</p>'
            f'<p>改答案，請使用橡皮擦擦拭乾淨，重新塗黑答案。例如答案為 <b class="tnr">B</b>，則</p>'
            f'<p>將 {_bubble("B")} 選項塗黑、塗滿，即：{_bubble("A")}{_bubble("", "full")}{_bubble("C")}{_bubble("D")}</p>'
            '</div><p class="outside">以下為錯誤的畫記方式，可能導致電腦無法正確判讀。如：</p><div class="indent">'
            + row([_bubble("A"), _bubble("B", "half"), _bubble("C"), _bubble("D")], "未將選項塗滿")
            + row([_bubble("A"), _bubble("B", "light"), _bubble("C"), _bubble("D")], "未將選項塗黑")
            + row([_bubble("A"), _bubble("", "full"), _bubble("C", "smudge"), _bubble("D")], "未擦拭乾淨")
            + row([_bubble("A"), _bubble("B", "over"), _bubble("C"), _bubble("D")], "塗出選項外")
            + row([_bubble("A"), _bubble("", "full"), _bubble("", "full"), _bubble("D")], "同時塗兩個選項"))


NOTES = {
    "國文": ("所有試題均為四選一的選擇題，答錯不倒扣，分為單題與題組兩個部分。",
            "題組是指共用問題情境的數道試題，包括「選文」及兩題以上的相關<br>試題。作答時請務必仔細閱讀選文的內容，再依問題做成判斷。",
            "部分試題中的詞語，將於該題右下角加註，以利參考。"),
    "英語": ("所有試題均為四選一的選擇題，答錯不倒扣。",
            "試題本分為單題和題組兩部分。",
            "部分試題中的單字或片語加註中文，以利參考。"),
    "社會": ("所有試題均為四選一的選擇題，答錯不倒扣。",
            "試題中所附圖形，如有附上比例尺，以比例尺為依據作答；若無<br>比例尺，則該圖僅作為參考，不代表實際大小。",
            "可利用試題本中空白部分計算，切勿在答案卡上計算。"),
}
NOTES["自然"] = NOTES["社會"]
VIOLATION = ("故意損壞試題本，或於{sheet}上挖補、汙損、折疊、作標記、顯示自己<br>"
             "身分，均屬違反試場規則行為，依簡章違規處理要點論處。")


def _choice_notice(subject: str) -> str:
    c = SUBJECTS[subject]
    start, end = c["clock"]
    name = {"英語": "英語科閱讀"}.get(subject, subject + "科")
    notes = [*NOTES[subject], VIOLATION.format(sheet=c["sheet"])]
    listed = "".join(f'<li><span class="n tnr">{i}.</span>{_times(n)}</li>' for i, n in enumerate(notes, 1))
    return (f'<div class="notice"><p class="h">測驗說明：</p><div class="indent">'
            + (f'<p>這是國中教育會考{name}試題本，試題本採雙面印刷，共 {_slot("pages")}頁，有</p>'
               f'<p>{_slot("items")}題選擇題，每題都只有一個正確或最佳的答案。測驗時間從 <b class="tnr">{start[:2]}</b>：<b class="tnr">{start[3:]}</b> 到</p>'
               if subject == "英語" else
               f'<p>這是國中教育會考{name}試題本，試題本採雙面印刷，共 {_slot("pages")}頁，有 {_slot("items")} 題</p>'
               f'<p>選擇題，每題都只有一個正確或最佳的答案。測驗時間從 <b class="tnr">{start[:2]}</b>：<b class="tnr">{start[3:]}</b> 到</p>')
            + f'<p><b class="tnr">{end[:2]}</b>：<b class="tnr">{end[3:]}</b>，共 <b class="tnr">{c["duration"]}</b> 分鐘。作答開始與結束請聽從監試委員的指示。</p></div>'
            f'<p class="h">注意事項：</p><ol>{listed}</ol><p class="h">作答方式：</p><div class="indent">'
            + _marking_example(c["sheet"]) + '</div></div>')


def _math_notice() -> str:
    c = SUBJECTS["數學"]
    start, end = c["clock"]
    notes = ("試題本的最後一頁附有參考公式可供作答使用。",
             "試題本分兩部分，第一部分為選擇題，第二部分為非選擇題。",
             "試題中參考的附圖，不一定代表實際大小。",
             "應試時可攜帶三角板、直尺、圓規，但不得攜帶量角器或附量角器功<br>能之文具，如有攜帶附量角器功能之任何文具，應於考試開始前放置<br>於試場前後方。",
             VIOLATION.format(sheet="答案卷").replace("顯示自己<br>身分", "顯示自<br>己身分"))
    listed = "".join(f'<li><span class="n tnr">{i}.</span>{_times(n)}</li>' for i, n in enumerate(notes, 1))
    return (f'<div class="notice math"><p class="h">測驗說明：</p><div class="indent">'
            f'<p>這是國中教育會考數學科試題本，試題本採雙面印刷，共 {_slot("pages")}頁，第一部分有</p>'
            f'<p>{_slot("items")}題選擇題，第二部分有 <b class="tnr">{c["constructed"]}</b> 題非選擇題。測驗時間從 '
            f'<b class="tnr">{start[:2]}</b>：<b class="tnr">{start[3:]}</b> 到 <b class="tnr">{end[:2]}</b>：<b class="tnr">{end[3:]}</b>，</p>'
            f'<p>共 <b class="tnr">{c["duration"]}</b>分鐘。作答開始與結束請聽從監試委員的指示。</p></div>'
            f'<p class="h gap">注意事項：</p><ol>{listed}</ol><p class="h gap">作答方式：</p>'
            '<p class="h">第一部分選擇題：</p><ol>'
            '<li><span class="n tnr">1.</span>作答選擇題時，可利用試題本中空白部分計算，切勿在答案卷上計算。</li>'
            '<li><span class="n tnr">2.</span>請依照題意從四個選項中選出一個正確或最佳的答案，並用<b class="tnr">2B</b>鉛筆<br>'
            '在答案卷上相應的位置畫記，請務必將選項塗黑、塗滿。如果需要修<br>'
            '改答案，請使用橡皮擦擦拭乾淨，重新塗黑答案。例如答案為<b class="tnr">B</b>，則<br>'
            f'將 {_bubble("B")} 選項塗黑、塗滿，即：{_bubble("A")}{_bubble("", "full")}{_bubble("C")}{_bubble("D")}</li></ol>'
            '<p class="h">第二部分非選擇題：</p><ol>'
            '<li><span class="n tnr">1.</span>不必抄題。</li>'
            '<li><span class="n tnr">2.</span>請依題意將解答過程及最後結果，用黑色墨水的筆清楚完整地寫在答案<br>'
            '卷上相應的欄位內，切勿寫出欄位外。若解答過程使用了題目敘述中沒<br>'
            '有出現的符號，則必須說明。如果需畫圖說明時，請用黑色墨水的筆，<br>'
            '將圖形畫在該題的欄位內。如需擬草稿，請使用試題本空白處。</li>'
            '<li><span class="n tnr">3.</span>更正時請使用修正帶(液)修正後，重新書寫解答過程。</li></ol></div>')


def _writing_notice() -> str:
    c = SUBJECTS["寫作測驗"]
    start, end = c["clock"]
    notes = ("不必訂題。", "請用本國文字書寫。", "不得使用詩歌體。",
             "請於寫作測驗答案卷上作答，且不得要求增加答案卷。如需擬草稿，<br>可使用試題本空白頁。",
             "作答時，書寫內容不得超出答案卷格線外框，且應使用黑色墨水的<br>筆，更正時，可以使用修正帶（液）。如有超出格線外框、書寫不清<br>"
             "或汙損等情事，致電腦掃描後無法清晰呈現作答結果者，其責任由考<br>生自負，不得提出異議。",
             VIOLATION.format(sheet="答案卷").replace("顯示自己<br>身分", "顯示自<br>己身分"))
    listed = "".join(f'<li><span class="n tnr">{i}.</span>{_times(n)}</li>' for i, n in enumerate(notes, 1))
    sheet = ('<div class="sheet-demo"><div class="demo-page"><span class="demo-label">第二頁</span></div>'
             '<div class="demo-page first"><span class="demo-start">↓</span><span class="demo-label">第一頁</span></div></div>')
    return (f'<p class="writing-lead">本測驗僅有<span class="tnr">1</span>題，作答時請使用寫作測驗答案卷，並從第一頁右邊第<span class="tnr">1</span>行<br>'
            f'開始作答。你可參考下面圖例：</p>{sheet}'
            f'<div class="notice writing"><p class="h">測驗說明：</p><div class="indent">'
            '<p>這是國中教育會考寫作測驗試題本，僅有<span class="tnr">1</span> 題，提供答案卷 <span class="tnr">1</span> 張，共 <span class="tnr">2</span> 頁。</p>'
            f'<p>測驗時間從 <span class="tnr">{start[:2]}</span>：<span class="tnr">{start[3:]}</span> 到 '
            f'<span class="tnr">{end[:2]}</span>：<span class="tnr">{end[3:]}</span>，共 <span class="tnr">{c["duration"]}</span> 分鐘。作答開始與結束請聽從監試委</p>'
            '<p>員的指示。作答時，請從答案卷第一頁右邊第 <span class="tnr">1</span> 行開始作答。</p></div>'
            f'<p class="h">注意事項：</p><ol>{listed}</ol><p class="h">作答方式：</p><div class="indent">'
            '<p><b>請依據題意要求完成寫作。</b></p></div></div>')


COVER_CSS = r"""
@page { size:A4; margin:0; }
* { box-sizing:border-box; }
html,body { margin:0; padding:0; background:#fff; color:#000; }
.sheet { position:relative; width:595.28pt; height:841.89pt; overflow:hidden; background:#fff; }
.sheet:not(:last-child) { break-after:page; }
.cap-cover { font-family:"DFKai-SB","BiauKai","BiauKaiTC","KaiTi",serif; font-size:13.25pt; }
.cap-cover .tnr { font-family:"Times New Roman",serif; }
.cap-cover .brand { position:absolute; left:0; right:0; top:26pt; text-align:center; font:11pt "Times New Roman",serif; color:#000; }
.cap-cover .title-slot { position:absolute; left:70pt; right:70pt; top:51pt; height:36pt; }
.cap-cover .subject { position:absolute; left:0; right:0; top:99pt; text-align:center;
  font:700 25pt/30pt "DFLiSong","PMingLiU","LiSong Pro","Songti TC",serif; letter-spacing:9pt; padding-left:9pt; }
.cap-cover .alert { position:absolute; left:70.6pt; width:452.7pt; top:140.9pt; height:91.2pt; border:.85pt solid #000; }
.cap-cover.writing .alert { left:71.3pt; top:134.9pt; height:75.7pt; }
.cap-cover .alert .big { margin:0; text-align:center; font:700 18pt/26pt "DFKai-SB","BiauKai","BiauKaiTC",serif; }
.cap-cover .alert .big:first-child { margin-top:6pt; }
.cap-cover .alert .check { position:absolute; left:5.7pt; top:66pt; margin:0; font-size:13.25pt; }
.cap-cover.writing .alert .check { top:53pt; font-size:12.65pt; }
.cap-cover .lead { position:absolute; left:70.2pt; top:259pt; margin:0; }
.cap-cover.math .lead { top:248pt; font-size:12.65pt; }
.cap-cover .notice { position:absolute; left:70.2pt; width:453.6pt; top:280.7pt; height:440.7pt;
  border:.85pt solid #000; padding:2pt 6pt 0 7pt; line-height:19.4pt; }
.cap-cover .notice.math { top:268.4pt; height:452.7pt; font-size:13pt; line-height:15.4pt; padding-top:2pt; }
.cap-cover .notice.writing { left:71.3pt; width:452.7pt; top:420.8pt; height:295.3pt; font-size:13pt; line-height:16pt; }
.cap-cover .notice p { margin:0; white-space:nowrap; }
/* 115 sets a full 37-character line inside the box; this 標楷體 advances slightly wider. */
.cap-cover .notice { letter-spacing:-.42pt; }
.cap-cover .notice.math { letter-spacing:-.55pt; }
.cap-cover.subject-cap-chinese .notice { letter-spacing:-.6pt; }
.cap-cover .notice.writing { letter-spacing:-.3pt; }
.cap-cover.writing .alert .big { line-height:22pt; }
.cap-cover .writing-lead { letter-spacing:-.45pt; }
.cap-cover .notice .indent { padding-left:26pt; }
.cap-cover .notice p.h { margin:0; }
.cap-cover .notice p.h.gap { margin-top:14pt; }
.cap-cover .notice p.outside { margin-left:0; }
.cap-cover .notice ol { list-style:none; margin:0; padding:0 0 0 24pt; }
.cap-cover .notice li { position:relative; padding-left:13pt; white-space:nowrap; }
.cap-cover .notice li .n { position:absolute; left:0; }
.cap-cover .slot { display:inline-block; width:17pt; height:1em; vertical-align:baseline; }
.cap-cover .bubble { display:inline-flex; align-items:center; justify-content:center; width:11pt; height:11pt;
  margin:0 1.6pt; border:.6pt solid #000; border-radius:50%; font:7pt/1 "Times New Roman",serif; vertical-align:-1pt; }
.cap-cover .bubble.full { background:#000; }
.cap-cover .bubble.half { background:linear-gradient(90deg,#000 50%,#fff 50%); }
.cap-cover .bubble.light { background:#bbb; }
.cap-cover .bubble.smudge { background:#999; color:#000; }
.cap-cover .bubble.over { background:#000; box-shadow:2pt -1pt 0 1.5pt #000; color:#fff; }
.cap-cover .mark-row { margin:0 0 0 28pt !important; }
.cap-cover .mark-note { margin-left:4pt; }
.cap-cover .start { position:absolute; left:181.4pt; top:735.7pt; margin:0; font-size:14pt; line-height:16.8pt; }
.cap-cover.writing .start { top:730.4pt; }
.cap-cover .start b { font-weight:700; }
.cap-cover .boxes { position:absolute; left:462pt; top:735pt; display:flex; gap:3pt; }
.cap-cover .boxes span { display:block; width:22pt; height:26pt; border:.85pt solid #000; }
.cap-cover .writing-lead { position:absolute; left:70.9pt; top:213pt; margin:0; font-size:13pt; line-height:21pt; text-indent:25pt; }
.cap-cover .sheet-demo { position:absolute; left:72.3pt; top:252pt; display:flex; gap:4.5pt; }
.cap-cover .demo-page { position:relative; width:224pt; height:150.3pt; border:.6pt solid #000;
  background:repeating-linear-gradient(90deg,transparent 0 9pt,#888 9pt 9.3pt); }
.cap-cover .demo-label { position:absolute; left:0; right:0; bottom:-17pt; text-align:center; background:#fff; }
.cap-cover .demo-start { position:absolute; right:3pt; top:-2pt; font:700 14pt "Times New Roman",serif; }
.cap-inner .page-number { position:absolute; left:0; right:0; text-align:center; font-family:Arial,"Helvetica Neue",sans-serif; line-height:1; }
.cap-inner .turn { position:absolute; left:406pt; top:calc(770.8pt + var(--shift)); font:16pt/1 "DFKai-SB","BiauKai","BiauKaiTC",serif; }
.formula-head { position:absolute; left:65.2pt; top:53pt; font:13pt "DFKai-SB","BiauKai","BiauKaiTC",serif; }
.formula-box { position:absolute; left:65.2pt; width:468pt; top:75pt; border:.85pt solid #000; padding:8pt 10pt 10pt;
  font:13pt/24pt "DFKai-SB","BiauKai","BiauKaiTC",serif; }
.formula-box p { margin:0; white-space:nowrap; }
.formula-box p.sub { padding-left:19pt; }
.formula-box .mark { display:inline-block; width:19pt; font:12pt "Apple Symbols","Segoe UI Symbol",serif; }
.formula-box i { font:italic 700 14pt "Times New Roman",serif; }
.formula-box .m { font:700 14pt "Times New Roman",serif; }
.formula-box sup,.formula-box sub { font-size:9pt; line-height:0; }
.formula-box .fr { display:inline-flex; flex-direction:column; vertical-align:middle; text-align:center; line-height:16pt; margin:0 2pt; }
.formula-box .fr > span:first-child { border-bottom:.7pt solid #000; padding:0 2pt; }
.formula-box .rad { border-top:.7pt solid #000; padding-top:.5pt; }
"""


def cover_markup(subject: str, *, organization: str = "Taiwan Exam 模擬試題") -> str:
    """One locked cover. The composer fills the title line, page count and item count."""
    config = subject_config(subject)
    name = subject[len(EXAM):] if subject.startswith(EXAM) else subject
    kind = {"數學": "math", "寫作測驗": "writing"}.get(name, "choice")
    sheet = config["sheet"]
    if name == "數學":
        notice = _math_notice()
    elif name == "寫作測驗":
        notice = _writing_notice()
    else:
        notice = _choice_notice(name)
    lead = '' if name == "寫作測驗" else '<p class="lead">請閱讀以下測驗作答說明：</p>'
    return (f'<section class="sheet cap-cover {kind} subject-{config["slug"]}">'
            f'<div class="brand">{_e(organization)}</div><div class="title-slot"></div>'
            f'<div class="subject">{_e(config["title"])}</div>'
            '<div class="alert"><p class="big">請不要翻到次頁！</p>'
            '<p class="big">讀完本頁的說明，聽從監試委員的指示才開始作答！</p>'
            f'<p class="check">※請先確認你的{sheet}、准考證與座位號碼是否一致無誤。</p></div>'
            f'{lead}{notice}'
            '<p class="start">聽到<b>考試正式開始鐘聲響起後</b>，請於右側<br>方格內填寫准考證末兩碼，再翻頁作答。</p>'
            '<div class="boxes"><span></span><span></span></div></section>')


def footer_box(subject: str) -> tuple[float, float, float, float] | None:
    """Where the composer writes the centred page number (A4 coordinates)."""
    config = subject_config(subject)
    if config["footer_pt"] is None:
        return None
    top = config["footer_top"] + BOTTOM_SHIFT
    return (PAGE_W / 2 - 20, top - 1, PAGE_W / 2 + 20, top + config["footer_pt"] * 1.4)


def inner_markup(subject: str, *, turn: bool = False, body: str = "") -> str:
    """A blank inner page: no running header (115 會考 prints none), turn cue optional."""
    subject_config(subject)
    cue = f'<div class="turn">{TURN_CUE}</div>' if turn else ''
    return (f'<section class="sheet cap-inner" style="--shift:{BOTTOM_SHIFT:.2f}pt">'
            f'<main>{body}</main>{cue}</section>')


def _f(tex: str) -> str:
    """Tiny formula markup: letters italic, digits and operators bold upright (115 sets Times bold)."""
    out = []
    for token in re.findall(r"\^\{[^}]*\}|_\{[^}]*\}|\^.|_.|[A-Za-z]|[0-9]+|.", tex):
        if token[0] in "^_":
            inner = token[2:-1] if token[1] == "{" else token[1:]
            tag = "sup" if token[0] == "^" else "sub"
            out.append(f"<{tag}>{_f(inner)}</{tag}>")
        elif token.isalpha() and token.isascii():
            out.append(f"<i>{token}</i>")
        elif token.isspace():
            out.append(" ")
        else:
            out.append(f'<span class="m">{_e(token)}</span>')
    return "".join(out)


MARK = '<span class="mark">❏</span>'


def formula_markup() -> str:
    """The 115 數學 reference formulas (on the booklet's last page)."""
    frac_s = f'<span class="fr"><span>{_f("n (a_1 + a_n)")}</span><span>{_f("2")}</span></span>'
    root = f'<span class="fr"><span>{_f("−b±")}√<span class="rad">{_f("b^2 − 4ac")}</span></span><span>{_f("2a")}</span></span>'
    rows = [
        f'<p>{MARK}和的平方公式：{_f("( a + b )^2 = a^2 + 2ab + b^2")}</p>',
        f'<p class="sub">差的平方公式：{_f("( a − b )^2 = a^2 − 2ab + b^2")}</p>',
        f'<p class="sub">平方差公式：{_f("a^2 − b^2 = ( a + b )( a − b )")}</p>',
        f'<p>{MARK}若直角三角形兩股長為 {_f("a")}、{_f("b")}，斜邊長為 {_f("c")}，則 {_f("c^2 = a^2 + b^2")}</p>',
        f'<p>{MARK}若圓的半徑為 {_f("r")}，圓周率為 {_f("π")}，則圓面積 {_f("= πr^2")}，圓周長 {_f("= 2πr")}</p>',
        f'<p>{MARK}凸 {_f("n")} 邊形的內角和為 {_f("(n − 2) × 180°")}，{_f("n ≥ 3")}</p>',
        f'<p>{MARK}若一個等差數列的首項為 {_f("a_1")}，公差為 {_f("d")}，第 {_f("n")} 項為 {_f("a_n")}，前 {_f("n")} 項和為 {_f("S_n")}，</p>',
        f'<p class="sub">則 {_f("a_n = a_1 + (n − 1) d")}，{_f("S_n =")} {frac_s}</p>',
        f'<p>{MARK}若一個等比數列的首項為 {_f("a_1")}，公比為 {_f("r")}，第 {_f("n")} 項為 {_f("a_n")}，則 {_f("a_n = a_1r^{n − 1}")}</p>',
        f'<p>{MARK}一元二次方程式 {_f("ax^2 + bx + c = 0")} 的解為 {_f("x =")} {root}</p>',
    ]
    return '<div class="formula-head">參考公式：</div><div class="formula-box">' + "".join(rows) + '</div>'


def document(markup: str, *, title: str) -> str:
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>{_e(title)}</title>'
            f'<style>{COVER_CSS}</style></head><body>{markup}</body></html>')
