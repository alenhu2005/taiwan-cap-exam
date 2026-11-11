#!/usr/bin/env python3
"""Check final saved PDF bytes against canonical fixed GSAT or 會考 layers, offline.

This verifies template reuse and page furniture, not item quality or authorship.
No supplied composition report, output metadata or author-selected mask is trusted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import pymupdf
from fetch_hosted_template_assets import (CAP_PREFIX, DEFAULT_MAP, PRODUCTION_COMPONENTS, ROOT,  # noqa: F401 (re-exported)
                                          inner_component, is_math_key, map_for, production_records, verify)


def masked_pixels(page, regions, *, alpha=False):
    matrix = pymupdf.Matrix(1.5, 1.5)
    pix = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY, alpha=alpha)
    samples = bytearray(pix.samples)
    for region in regions:
        rect = (pymupdf.Rect(region) * matrix).irect & pix.irect
        if rect.is_empty:
            continue
        # PyMuPDF's set_rect currently loops through every sample in Python.
        # Whole scanline replacement preserves exactly the same integer bounds,
        # pixel values and comparison resolution without millions of callbacks.
        row = bytes([0 if alpha else 255]) * (rect.width * pix.n)
        for y in range(rect.y0, rect.y1):
            start = (y-pix.y)*pix.stride + (rect.x0-pix.x)*pix.n
            samples[start:start+len(row)] = row
    return bytes(samples)


SIGNATURE_REMINDER = '請記得在答題卷簽名欄位以正楷簽全名'


def answers_template(document):
    """The inner template as a solutions booklet prints it: without the grey signature
    reminder, which speaks to candidates at an answer sheet. Two hosted 數B audits flagged
    it on every page of the 詳解. Compose and verify both derive this same redacted copy."""
    copy = pymupdf.open()
    copy.insert_pdf(document, from_page=0, to_page=0)
    page = copy[0]
    boxes = page.search_for(SIGNATURE_REMINDER)
    # The grey band behind it, not the page's white background.
    boxes += [d['rect'] for d in page.get_drawings()
              if d.get('fill') and tuple(d['fill']) != (1.0, 1.0, 1.0) and d['rect'].height < 30
              and any(d['rect'].intersects(box) for box in boxes)]
    if not boxes:
        raise ValueError('inner template lacks the signature reminder it should carry')
    for box in boxes:
        page.add_redact_annot(pymupdf.Rect(box) + (-2, -2, 2, 2), fill=False)
    # Only graphics inside the boxes: the templates' full-page white ground must stay, or a
    # body drawn over it blends differently and the locked header pixels change.
    page.apply_redactions(images=0, graphics=1, text=0)
    # Balance the rewritten stream and re-parse it, so pages placed on it later draw the
    # same after saving as they did in memory.
    page.clean_contents()
    data = copy.tobytes(garbage=3, deflate=True)
    copy.close()
    return pymupdf.open(stream=data, filetype='pdf')


def streams(page):
    # Page content plus nested Form XObjects reachable from this page; document
    # attachments and unused objects elsewhere are not evidence of composition.
    refs = page.get_contents() + [row[0] for row in page.get_xobjects()]
    return {hashlib.sha256(page.parent.xref_stream(x)).hexdigest() for x in refs}


def field_pixels(page, box):
    return page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=pymupdf.Rect(box),
                           colorspace=pymupdf.csGRAY).samples


# Running-header digits and each booklet's footer page number, ROC 115 measured.
RUNNING_FOOTER_PT = {"國綜": 10.08, "國寫": 11.04, "英文": 9.96, "數學A": 10.02, "數學B": 10.02, "社會": 9.96, "自然": 10.98,
                     # 115 會考: one centred Arial page number per page (數學 13 pt, others 12 pt).
                     "會考國文": 12.0, "會考英語": 12.0, "會考數學": 13.0, "會考社會": 12.0, "會考自然": 12.0}
RUNNING_HEADER_PT = 11.04
# The page and item counts the composer prints inside a 會考 cover's 測驗說明.
COVER_COUNT_KEYS = ('cover_pages', 'cover_items')


def field_size(subject, key):
    """Dynamic digits at the official size: 11 pt header numbers, the booklet's footer size."""
    return RUNNING_FOOTER_PT[subject] if key == 'footer' else RUNNING_HEADER_PT


def glyphs_at(page, box):
    """Text whose glyph origins lie in `box`: neighbouring lines' tall glyph boxes are ignored."""
    rect = pymupdf.Rect(box)
    return ''.join(c['c'] for b in page.get_text('rawdict', clip=rect + (-2, -20, 2, 20))['blocks']
                   for l in b.get('lines', []) for s in l['spans'] for c in s['chars']
                   if c['c'].strip() and rect.contains(pymupdf.Point(c['origin'][0] + .1, c['origin'][1] - .5)))


def field_font(subject):
    """Page-number face: Times for 學測, Helvetica (Arial's metric twin) for 會考."""
    return 'helv' if subject.startswith(CAP_PREFIX) else 'tiro'


def expected_counter(box, text, size, face='tiro'):
    # Compare rendered digits. PDF text extraction can include invisible text
    # outside a clipped Form XObject, including the formula's original header.
    font = pymupdf.Font(face)
    rect = pymupdf.Rect(box)
    x = rect.x0 + (rect.width-font.text_length(text,fontsize=size))/2
    y = rect.y0 + (rect.height-size*(font.ascender-font.descender))/2 + size*font.ascender
    with pymupdf.open() as doc:
        page = doc.new_page(width=595.28,height=841.89)
        page.insert_font(fontname='Counter',fontbuffer=font.buffer)
        for character in text:
            page.insert_text((x,y),character,fontname='Counter',fontsize=size)
            x += font.text_length(character,fontsize=size)
        return field_pixels(page,box)


def verify_pdf(pdf: Path, subject: str, kind: str, asset_dir: Path | None = None) -> dict:
    errors, pages, assets = [], [], {}
    report = {'status': 'fail-fixed-template', 'subject': subject, 'kind': kind,
              'errors': errors, 'pages': pages, 'scope': 'Fixed PDF layers only; no academic acceptance.'}
    try:
        if kind not in {'questions', 'answers'}:
            raise ValueError('kind must be questions or answers')
        cap = subject.startswith(CAP_PREFIX)
        manifest = json.loads(map_for(subject).read_text(encoding='utf-8-sig'))
        record = next((r for r in manifest['subjects'] if r['subject'] == subject), None)
        if record is None:
            raise ValueError('unsupported fixed-template subject')
        geometry = record['overlay_geometry_pt']
        for asset in production_records(record):
            component = asset['component']
            path = asset_dir / (component + '.pdf') if asset_dir else ROOT / asset['repository_path']
            data = path.read_bytes()
            verify(asset, data)
            assets[component] = pymupdf.open(stream=data, filetype='pdf')
            if kind == 'answers' and component.startswith('inner-') and not cap:
                original = assets[component]
                assets[component] = answers_template(original)
                original.close()
        data = pdf.read_bytes()
        report['pdf_sha256'] = hashlib.sha256(data).hexdigest()
        math_formula = is_math_key(subject) and kind == 'questions'
        offset = int(kind == 'questions')
        cover_masks = [geometry['cover_title'], *(geometry[k] for k in COVER_COUNT_KEYS if k in geometry)]
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            total = len(doc) - offset
            body_pages = total - int(math_formula)
            if total < 1 + int(math_formula):
                errors.append('missing cover/body/formula pages')
            baselines = {}
            for index, page in enumerate(doc):
                number = index + 1 - offset
                cover = offset and index == 0
                parity = 'odd' if number % 2 else 'even'
                component = 'cover-blank' if cover else inner_component(record, number, body_pages, kind)
                base = assets[component][0]
                fields = {} if cover else geometry[parity]
                masks = cover_masks if cover else [geometry['body'], *fields.values()]
                findings = []
                if page.rotation or abs(page.rect.width-base.rect.width) > .01 or abs(page.rect.height-base.rect.height) > .01:
                    findings.append('page-size-or-rotation')
                if component not in baselines:
                    baselines[component] = masked_pixels(base, masks)
                if masked_pixels(page, masks) != baselines[component]:
                    findings.append('locked-pixels-changed')
                reachable = streams(page)
                if not streams(base).issubset(reachable):
                    findings.append('original-template-stream-missing')
                if cover:
                    if not page.get_textbox(pymupdf.Rect(geometry['cover_title'])).strip():
                        findings.append('missing-dynamic-cover-title')
                    for key in COVER_COUNT_KEYS:
                        if key in geometry:
                            printed = glyphs_at(page, geometry[key])
                            if not printed.isdigit() or (key == 'cover_pages' and printed != str(total)):
                                findings.append('incorrect-dynamic-' + key)
                else:
                    for key, box in fields.items():
                        text = ''.join(page.get_textbox(pymupdf.Rect(box)).split())
                        expected = str(total) if key == 'total_pages' else str(number)
                        wrong = (not text or field_pixels(page,box)==field_pixels(base,box)) if key == 'year_name' else (
                            field_pixels(page,box) != expected_counter(box,expected,field_size(subject,key),field_font(subject)))
                        if wrong:
                            findings.append('incorrect-dynamic-' + key)
                formula = math_formula and index == len(doc)-1
                if formula:
                    original = assets['formula-blank'][0]
                    box = pymupdf.Rect(geometry['body'])
                    def pixels(p):
                        return p.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=box,
                                            colorspace=pymupdf.csGRAY).samples
                    if pixels(page) != pixels(original):
                        findings.append('original-formula-body-changed')
                    if not streams(original).issubset(reachable):
                        findings.append('original-formula-stream-missing')
                pages.append({'page': index+1, 'component': component, 'formula': bool(formula), 'errors': findings})
                errors.extend(f'page-{index+1}: {finding}' for finding in findings)
        report['status'] = 'pass-fixed-template' if not errors else 'fail-fixed-template'
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        errors.append(f'cannot verify fixed template: {exc}')
    finally:
        for doc in assets.values():
            doc.close()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--kind', required=True, choices=('questions', 'answers'))
    parser.add_argument('--asset-dir', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify_pdf(args.pdf, args.subject, args.kind, args.asset_dir)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    print(text)
    raise SystemExit(0 if result['status'] == 'pass-fixed-template' else 2)
