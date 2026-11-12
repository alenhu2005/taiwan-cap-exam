"""國中教育會考: template map, composition, body rendering, form gate and calibration.

Synthetic layout fixtures only: placeholder wording, never exam questions.
"""
import hashlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_hosted_workflow as workflow
import cap_plan
from compose_hosted_pdf import compose
from fetch_hosted_template_assets import (CAP_MAP, DEFAULT_MAP, inner_component, map_for, production_records,
                                          style_subject, template_key)
from hosted_body_templates import render
from hosted_calibration import CAP_SUBJECTS, snapshot
from hosted_density import page_role
from hosted_subject_gates import subject_gate_errors
from validate_cap_form import OFFICIAL_RANGES, validate_exam
from hosted_blind_review import cap_p_band
from verify_fixed_template_pdf import verify_pdf

CAP_MAP_DATA = json.loads(CAP_MAP.read_text(encoding='utf-8'))
RECORDS = {r['subject']: r for r in CAP_MAP_DATA['subjects']}
PLACEHOLDER = '合成題幹，用於測試會考版面。'
COMPETENCY = {'context_type': '生活情境', 'process': '推論', 'real_world_anchor': '合成情境錨點',
              'evidence_link': '合成：答案取決於材料中的證據', 'prerequisite_knowledge': ['合成先備概念']}


def asset_dir(key):
    return ROOT / Path(RECORDS[key]['assets'][0]['repository_path']).parent


@pytest.fixture(scope='module')
def font(tmp_path_factory):
    path = tmp_path_factory.mktemp('font') / 'font.ttf'
    path.write_bytes(pymupdf.Font('cjk').buffer)
    return path


def body_pdf(path, pages, key):
    box = RECORDS[key]['overlay_geometry_pt']['body']
    with pymupdf.open() as doc:
        for index in range(pages):
            page = doc.new_page(width=595.28, height=841.89)
            page.insert_text((box[0] + 5, box[1] + 20), f'synthetic body {index + 1}', fontsize=12)
        doc.save(path)
    return path


def test_cap_keys_never_resolve_to_gsat_records():
    assert template_key('會考', '社會') == '會考社會' and template_key('學測', '社會') == '社會'
    assert map_for('會考社會') == CAP_MAP and map_for('社會') == DEFAULT_MAP
    gsat = {r['subject'] for r in json.loads(DEFAULT_MAP.read_text(encoding='utf-8'))['subjects']}
    assert not gsat & set(RECORDS)
    assert set(RECORDS) == set(CAP_SUBJECTS)
    assert style_subject('會考國文') == '國綜' and style_subject('數學A') == '數學A'


def test_cap_map_records_match_checked_in_bytes():
    for record in CAP_MAP_DATA['subjects']:
        for asset in record['assets']:
            data = (ROOT / asset['repository_path']).read_bytes()
            assert len(data) == asset['bytes'] and hashlib.sha256(data).hexdigest() == asset['sha256']
        components = {r['component'] for r in production_records(record)}
        assert {'cover-blank', 'inner-odd-blank', 'inner-even-blank'} <= components
        assert ('formula-blank' in components) == (record['subject'] == '會考數學')
        assert ('inner-even-turn-blank' in components) == (record['subject'] != '會考寫作測驗')
    assert CAP_MAP_DATA['asset_count'] == sum(len(r['assets']) for r in CAP_MAP_DATA['subjects'])


def test_turn_cue_only_on_even_pages_before_the_last_question_page():
    record = RECORDS['會考國文']
    picked = [inner_component(record, n, 6, 'questions') for n in range(1, 7)]
    assert picked == ['inner-odd-blank', 'inner-even-turn-blank', 'inner-odd-blank', 'inner-even-turn-blank',
                      'inner-odd-blank', 'inner-even-blank']
    assert all('turn' not in inner_component(record, n, 6, 'answers') for n in range(1, 7))
    assert inner_component(RECORDS['會考寫作測驗'], 2, 4, 'questions') == 'inner-even-blank'


@pytest.mark.parametrize('key', sorted(RECORDS))
@pytest.mark.parametrize('kind', ['questions', 'answers'])
def test_every_cap_booklet_composes_and_verifies(key, kind, font, tmp_path):
    body = body_pdf(tmp_path / 'body.pdf', 3, key)
    output = tmp_path / f'{kind}.pdf'
    result = compose(key, body, asset_dir(key), output, year='116', title='國中教育會考模擬試題', running_name='會考',
                     font_path=font, kind=kind, item_count=42)
    report = verify_pdf(output, key, kind, asset_dir(key))
    assert report['status'] == 'pass-fixed-template', report['errors']
    formula = key == '會考數學' and kind == 'questions'
    assert len(result['pages']) == 3 + int(formula) + int(kind == 'questions')
    with pymupdf.open(output) as doc:
        if kind == 'questions':
            cover = doc[0].get_text()
            assert '116' in cover and '國中教育會考模擬試題' in cover and 'Taiwan Exam' in cover
        if formula:
            assert '參考公式' in doc[-1].get_text()
        turn = [i for i, page in enumerate(doc) if '請翻頁繼續作答' in page.get_text()]
        assert turn == ([2] if kind == 'questions' and key != '會考寫作測驗' else [])


def test_cover_counts_and_page_numbers_are_checked(font, tmp_path):
    key = '會考社會'
    body = body_pdf(tmp_path / 'body.pdf', 2, key)
    with pytest.raises(ValueError, match='item_count'):
        compose(key, body, asset_dir(key), tmp_path / 'none.pdf', year='116', title='國中教育會考模擬試題',
                running_name='會考', font_path=font, kind='questions')
    good = tmp_path / 'good.pdf'
    compose(key, body, asset_dir(key), good, year='116', title='國中教育會考模擬試題', running_name='會考',
            font_path=font, kind='questions', item_count=54)
    with pymupdf.open(good) as doc:
        page = doc[1]
        page.insert_text((300, 795), '9', fontsize=12)   # a stray digit on the page number
        doc.save(tmp_path / 'bad.pdf')
    report = verify_pdf(tmp_path / 'bad.pdf', key, 'questions', asset_dir(key))
    assert report['status'] == 'fail-fixed-template'


def cap_paper(key, root):
    """A synthetic full-count 會考 paper in the maintained exam.json conventions."""
    subject = key[2:]
    if key == '會考寫作測驗':
        questions = [{'id': 'w1', 'number': 1, 'type': 'guided_writing',
                      'number_display': '', 'prompt': '請先閱讀以下資訊，並依據題意要求完成一篇文章。\n\n' + PLACEHOLDER * 6
                      + '\n請結合你的經驗或見聞，寫下對此的感受、想法。\n※不必訂題\n※不可在文中洩漏私人身分\n※不可使用詩歌體'}]
        sections = []
        answers = [{'question_id': 'w1', 'final_answer': '依六級分規準評閱',
                    'reasoning': ['合成審題說明。', '立意取材：合成。結構組織：合成。遣詞造句：合成。錯別字、格式與標點符號：合成。']}]
        return {'metadata': {'exam': '會考', 'subject': key}, 'sections': sections, 'questions': questions, 'answers': answers}
    count = {'會考國文': 42, '會考英語': 43, '會考數學': 25, '會考社會': 54, '會考自然': 50}[key]
    stem = 'Read the note and choose the best answer.' if key == '會考英語' else PLACEHOLDER
    plan_slots = cap_plan.plan(key, 'fixture', seed='fixture')['planning_slots']
    units = {s['number']: s.get('unit') or s.get('domain') for s in plan_slots}
    targets = cap_plan.position_targets(key, '會考')
    keys = 'ABCD' * 20
    order = [keys[(i * 3 + i // 4) % 4] for i in range(count)]
    questions, answers = [], []
    for n in range(1, count + 1):
        key_label = order[n - 1]
        competency = {**COMPETENCY,
                      # 會考社會 單題 alternate 歷史／地理／公民 in short runs, as 115 prints them; 自然 domains
                      # follow the plan's official shares.
                      'domain': ('歷史', '地理', '公民')[(n // 2) % 3] if key == '會考社會' else
                                units[n] if key == '會考自然' else '',
                      'hidden_concept': f'合成目標概念{n}', 'bridge': '合成：答案同時需要兩個概念'}
        if key == '會考數學':
            # 113-115: three direct openings, about a third situated, two items judging two people's claims.
            competency['context_type'] = '生活情境' if n > 3 and n % 2 else '學科知識'
            competency['process'] = '評鑑' if n in (14, 20) else competency['process']
        if key == '會考自然':
            # 113-115: experiments every year, at least one judgement of another's claim.
            competency['context_type'] = '科學探究' if n % 6 == 0 else competency['context_type']
            competency['process'] = '評鑑' if n in (9, 22) else competency['process']
        if key == '會考英語' and n > count - 24:
            competency['process'] = ('擷取訊息', '推論', '統整解釋', '應用')[n % 4]
        if n % 4 == 0 and key in ('會考社會',):
            competency['domains'] = [competency['domain'], '公民' if competency['domain'] != '公民' else '地理']
        q = {'id': f'q{n}', 'number': n, 'section_id': 's1', 'type': 'single_choice',
             'prompt': f'{stem}（{n}）', 'options': [{'label': c, 'text': f'合成選項{c}{n}'} for c in 'ABCD'],
             'item_spec': {'cap_competency': competency,
                           **({'cap_unit': units[n]} if key in ('會考數學', '會考國文', '會考英語') else {}),
                           'curriculum_codes': ['Ea-IV-1', 'Mb-IV-2'] if n % 4 == 0 else ['Ea-IV-1'],
                           'textbook_volumes': [('第一冊', '第二冊', '第三冊', '第四冊', '第五冊', '第六冊')[n % 6]]
                                                if key == '會考自然' else ['第三冊'],
                           'cap_distractors': {c: {'misconception': '合成迷思', 'peer_concept': '合成相鄰概念',
                                                   'expected_pick_rate': 0.12, 'ruled_out_by': '合成：課本定義排除'}
                                               for c in 'ABCD' if c != key_label},
                           'difficulty_design': {'linked_decisions': ['合成判斷一', '合成判斷二'],
                                                 'estimated_p': targets[n]['target_p']}}}
        if key in ('會考社會', '會考自然') and n in (5, 9, 13):
            # 圖形選項: four figures as the options (official 社會 1-3, 自然 4 a year).
            q['inline_assets'] = {}
            for c in 'ABCD':
                path = Path(root) / f'opt-{n}-{c}.svg'
                path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="110"><path d="M10 100 L150 '
                                f'{10 + "ABCD".index(c) * 20}" stroke="black"/></svg>', encoding='utf-8')
                q['inline_assets'][f'opt{n}{c}'] = {'path': path.name, 'width_pt': 120,
                                                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                q['options']['ABCD'.index(c)]['text'] = '{{asset:opt' + f'{n}{c}' + '}}'
        if n in (count - 1, count):
            q['group_stimulus'] = PLACEHOLDER * 5
        if key == '會考英語' and n == 1:
            # 113-115 open the 單題 with a picture item.
            path = Path(root) / 'picture-1.svg'
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="90"><rect x="10" y="10" '
                            'width="140" height="70" fill="none" stroke="black"/></svg>', encoding='utf-8')
            q['visual_asset'] = {'path': path.name, 'width_percent': 30, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                 'visual_spec': {'kind': 'diagram', 'semantic_data': {}}}
        questions.append(q)
        option = q['options']['ABCD'.index(order[n - 1])]['text']
        if option.startswith('{{asset:'):
            option = f'圖形選項({order[n - 1]})'
        answers.append({'question_id': q['id'], 'final_answer': order[n - 1],
                        'reasoning': ['合成步驟一：由材料讀出關鍵證據。',
                                      f'合成步驟二：因為{option}符合題意，故選({key_label})。',
                                      '其餘選項：' + '、'.join(f'({c})合成錯因' for c in 'ABCD' if c != key_label) + '。']})
    sections = [{'id': 's1', 'title': '一、單題', 'instructions': []}]
    if key == '會考數學':
        sections.append({'id': 's2', 'title': '第二部分：非選擇題（1～2題）', 'instructions': []})
        for n in (1, 2):
            questions.append({'id': f'c{n}', 'number': count + n, 'number_display': f'{n}.', 'section_id': 's2',
                              'answer_label': f'非選擇題第{n}題',
                              'type': 'constructed_response', 'prompt': '合成非選擇題，請寫出完整的解題過程。',
                              'item_spec': {'cap_competency': COMPETENCY, 'curriculum_codes': ['N-8-1']}})
            answers.append({'question_id': f'c{n}', 'final_answer': '見詳解',
                            'reasoning': ['合成步驟一。', '合成步驟二。', '合成步驟三。'],
                            'rubric': {'3': '完整正確', '2': '主要步驟正確', '1': '部分概念正確', '0': '空白或錯誤'}})
    return {'metadata': {'exam': '會考', 'subject': key}, 'sections': sections, 'questions': questions, 'answers': answers}


@pytest.mark.parametrize('key', sorted(RECORDS))
def test_cap_form_gate_accepts_the_official_shape(key, tmp_path):
    exam = cap_paper(key, tmp_path)
    assert validate_exam(exam) == []
    gate = subject_gate_errors(exam)
    # No 學測 subject validator (social/natural/literacy/english layout) runs on a 會考 paper.
    assert not [e for e in gate if not e.startswith(('cap-form', 'answers', 'answer-key'))], gate
    assert not [e for e in gate if e.startswith('cap-form')], gate


def test_cap_form_gate_rejects_off_form_papers(tmp_path):
    exam = cap_paper('會考社會', tmp_path)
    exam['questions'][0]['options'].append({'label': 'E', 'text': '第五個選項'})
    exam['questions'] = exam['questions'][:40]
    errors = validate_exam(exam)
    assert any('four options' in e for e in errors) and any('50-60' in e for e in errors)
    math = cap_paper('會考數學', tmp_path)
    del next(a for a in math['answers'] if a['question_id'] == 'c1')['rubric']
    assert any('rubric' in e for e in validate_exam(math))
    english = cap_paper('會考英語', tmp_path)
    english['questions'][0]['type'] = 'listening_choice'
    assert any('聽力' in e for e in validate_exam(english))
    assert OFFICIAL_RANGES['會考數學'] == (23, 28)


@pytest.mark.parametrize('key', sorted(RECORDS))
def test_cap_papers_project_render_and_compose(key, font, tmp_path):
    exam = cap_paper(key, tmp_path)
    body = RECORDS[key]['overlay_geometry_pt']['body']
    questions, solutions = workflow.project_specs(exam, {}, body[2] - body[0] - 8)
    assert questions['subject'] == key and solutions['subject'] == key
    ids = {q['id'] for q in exam['questions']}
    for name, spec, kind in (('q', questions, 'questions'), ('s', solutions, 'answers')):
        layout = render(spec, tmp_path / f'{name}-body.pdf', tmp_path / f'{name}.json', font, asset_root=tmp_path)
        covered = {p['id'] for p in layout['parts']} | {c for p in layout['parts'] for c in p.get('covers', [])}
        assert covered == ids
        output = tmp_path / f'{name}.pdf'
        compose(key, tmp_path / f'{name}-body.pdf', asset_dir(key), output, year='116', title='國中教育會考模擬試題',
                running_name='會考', font_path=font, kind=kind,
                item_count=sum(q['type'] == 'single_choice' for q in exam['questions']) or None)
        assert verify_pdf(output, key, kind, asset_dir(key))['status'] == 'pass-fixed-template'
    if key in {'會考國文', '會考社會', '會考自然', '會考數學'}:
        labels = [b.get('group_label') for b in questions['blocks'] if b.get('group_label')]
        n = sum(q['type'] == 'single_choice' for q in exam['questions'])
        assert labels and str(n - 1) in labels[0] and '為題組' not in labels[0]


@pytest.mark.parametrize('key', CAP_SUBJECTS)
def test_cap_calibration_snapshot_is_bound_to_official_sources(key):
    calibration = snapshot(key)
    assert calibration['exam'] == '會考' and calibration['paper_profile']['structure_status'] == 'verified'
    baseline = json.loads((ROOT / 'exam_packs/會考/official-baseline.json').read_text(encoding='utf-8'))
    hashes = {s['sha256'] for s in baseline['sources']}
    assert all(p['source_sha256'] in hashes for p in calibration['page_metrics'])
    if key == '會考寫作測驗':
        assert calibration['objective_profile'] is None and calibration['writing_rubric']
    else:
        years = calibration['objective_profile']['years']
        assert set(years) == {'113', '114', '115'}
        assert all(len(y['by_position']) == baseline['subjects'][key[2:]]['years'][year]['choice_items']
                   for year, y in years.items())


def test_cap_delivery_names_print_the_subject_once():
    metadata = {'exam': '會考', 'subject': '會考社會'}
    assert workflow.delivery_filename(metadata, '20261110-01', 'question') == '會考_社會_20261110-01_題本.pdf'


def test_cap_cover_and_formula_pages_are_fixed_layers():
    assert page_role('請不要翻到次頁！', 1, 9, '會考數學') == 'cover'
    assert page_role('參考公式：', 9, 9, '會考數學') == 'formula'


def test_cap_quality_gates(tmp_path):
    """素養 records, situated share, disclaimers, plain labels and longest-option keys."""
    exam = cap_paper('會考自然', tmp_path)
    exam['questions'][3]['prompt'] = '以下為教學模型，非真實數據：' + exam['questions'][3]['prompt']
    exam['questions'][4]['options'][0]['label'] = '(A)'
    for q in exam['questions'][10:40]:
        q['item_spec']['cap_competency'] = {**COMPETENCY, 'context_type': '學科知識'}
    del exam['questions'][5]['item_spec']['cap_competency']
    for q, a in zip(exam['questions'][:20], exam['answers'][:20]):
        a['final_answer'] = 'A'
        q['options'][0]['text'] = '這是明顯比其他選項都長很多的正確答案敘述內容'
    errors = validate_exam(exam)
    for needle in ('教學模型', 'plain A, B, C, D', 'cap_competency is required', 'real situation', 'single longest option'):
        assert any(needle in e for e in errors), (needle, errors)


def test_cap_difficulty_review_needs_official_p_and_discrimination(tmp_path):
    from hosted_blind_review import CAP_MEAN_D, CAP_MEAN_P, review_errors
    assert set(CAP_MEAN_P) == set(CAP_MEAN_D) == set(OFFICIAL_RANGES)
    exam = cap_paper('會考社會', tmp_path)   # writes option figures: never into the repository
    def errors(p, d):
        rows = [{'id': q['id'], 'estimated_p': p, 'estimated_d': d} for q in exam['questions']]
        return [e for e in review_errors(exam, {'items': rows}) if '通過率' in e or '鑑別度' in e]
    assert errors(0.66, 0.50) == []
    assert any('outside the 會考 band' in e for e in errors(0.85, 0.50))
    assert any('below the best official' in e for e in errors(0.66, 0.30))
    assert any('鑑別度 below 0.30' in e for e in errors(0.66, 0.20))


def test_cap_levels_stay_in_scope_and_show_derivations(tmp_path):
    from hosted_blind_review import cap_p_band
    exam = cap_paper('會考數學', tmp_path)
    exam['metadata']['cap_difficulty_level'] = '極難'
    for a in exam['answers']:
        if a['question_id'].startswith('q'):
            a['reasoning'] = a['reasoning'][:2]
    exam['questions'][0]['item_spec']['curriculum_codes'] = ['N-10-1']
    exam['questions'][1]['item_spec']['cap_competency'] = {**COMPETENCY, 'prerequisite_knowledge': []}
    errors = validate_exam(exam)
    assert any('第四學習階段' in e for e in errors)
    assert any('prerequisite_knowledge' in e for e in errors)
    assert sum('reasoning step' in e for e in errors) == 25   # 極難 needs three written steps per choice item
    exam['metadata']['cap_difficulty_level'] = '超難'
    assert any('cap_difficulty_level' in e for e in validate_exam(exam))
    bands = [cap_p_band('會考自然', level) for level in ('會考', '中', '高', '極難')]
    assert all(a[0] == b[1] for a, b in zip(bands, bands[1:]))   # contiguous, each harder than the last


def test_cap_quality_gates_catch_the_reviewed_defects(tmp_path):
    """Defects a maintainer review found in hosted 會考社會 papers (soc01, cap116a), each caught on save."""
    from validate_cap_quality import validate_items
    exam = cap_paper('會考社會', tmp_path)
    q = {x['id']: x for x in exam['questions']}
    key = {a['question_id']: a['final_answer'] for a in exam['answers']}
    def set_key(qid, label, text):
        q[qid]['options']['ABCD'.index(label)]['text'] = text
        next(a for a in exam['answers'] if a['question_id'] == qid)['final_answer'] = label
    # soc01 Q12: the figure's caption printed the key verbatim.
    set_key('q12', 'B', '供給曲線向左移動且市場價格上漲')
    figure = tmp_path / 'supply.svg'
    figure.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>天災減產導致供給曲線向左移動，均衡價格上漲</text></svg>',
                      encoding='utf-8')
    q['q12']['visual_asset'] = {'path': 'supply.svg', 'visual_spec': {}}
    # soc01 Q4/Q30: absurd extreme distractors.
    q['q4']['options'][3 if key['q4'] != 'D' else 0]['text'] = '全年的日照時數與降水量急速歸零'
    # cap116a Q46/Q50: counting shaded bars; long division.
    q['q16']['prompt'] = '圖中所列的九個縣市裡，65歲以上人口比率已達20%以上的共有幾個？'
    q['q20']['prompt'] = '平均每個投票所約服務多少位選舉人（四捨五入至百位）？'
    # soc01 group pages: the lead-in typed into the material as well as printed by the renderer.
    q['q53']['group_stimulus'] = '閱讀下列選文，回答第 53 至 54 題：' + q['q53']['group_stimulus']
    # The concept to infer printed in the stem.
    q['q7']['prompt'] = '依據三省六部的分工，下列何者正確？'
    q['q7']['item_spec']['cap_competency'] = {**q['q7']['item_spec']['cap_competency'], 'hidden_concept': '三省六部'}
    # A distractor without its misconception record.
    wrong = next(c for c in 'ABCD' if c != key['q9'])
    q['q9']['item_spec']['cap_distractors'][wrong] = {'misconception': ''}
    # cap116a Q6/Q31: common-sense absurdities in distractors; Q37: an explanation silent on rival options.
    q['q10']['item_spec']['cap_distractors'][next(c for c in 'ABCD' if c != key['q10'])]['expected_pick_rate'] = 0.01
    next(a for a in exam['answers'] if a['question_id'] == 'q11')['reasoning'] = ['只說明正解。', '故選此項。']
    for n, x in enumerate(exam['questions'][:24]):
        x['item_spec']['difficulty_design'] = {'linked_decisions': ['只有一個判斷']}
    for x in exam['questions'][20:26]:
        x['options'][next(i for i, c in enumerate('ABCD') if c != key[x['id']])]['text'] = '憲法只保障稱讚他人的言論'
    errors = validate_items(exam, asset_root=tmp_path)
    q['q30']['prompt'] = '某地名中的「坑頭」與「坑尾」反映了什麼？'
    errors = validate_items(exam, asset_root=tmp_path)
    for needle in ('reuses the setting', 'prints the answer', 'extreme wording', 'count things', 'arithmetic exercise', 'lead-in',
                   'must infer', 'cap_distractors.' + wrong, 'draw 1%', 'never addresses option',
                   'fewer than two linked decisions', 'absolute words'):
        assert any(needle in e for e in errors), (needle, errors)
    # cap116a: 歷史 1-15, 地理 16-29, 公民 30-43 in three solid blocks.
    blocks = cap_paper('會考社會', tmp_path)
    for x in blocks['questions'][:43]:
        domain = '歷史' if x['number'] <= 15 else '地理' if x['number'] <= 29 else '公民'
        x['item_spec']['cap_competency'] = {**x['item_spec']['cap_competency'], 'domain': domain, 'domains': [domain]}
    assert any('run in blocks' in e for e in validate_items(blocks))
    # The synthetic paper itself meets every floor.
    assert validate_items(cap_paper('會考社會', tmp_path)) == []


@pytest.mark.parametrize('key', sorted(RECORDS))
@pytest.mark.parametrize('level', ['會考', '極難'])
def test_cap_plan_follows_the_official_structure(key, level):
    from cap_plan import check, item, plan
    from validate_cap_quality import MAX_RUN, MIN_SWITCHES
    result = plan(key, f'seed-{key}-{level}', level=level)
    # Same paper_id, new draw each time; the saved seed reproduces a paper's draw.
    again = plan(key, f'seed-{key}-{level}', level=level)
    assert result['metadata']['variety_seed'] != again['metadata']['variety_seed']
    if key not in ('會考寫作測驗',):
        same = plan(key, 'x', level=level, seed=result['metadata']['variety_seed'])
        assert [s.get('suggested_focus') for s in same['planning_slots']] == [s.get('suggested_focus') for s in result['planning_slots']]
    assert result['metadata']['exam'] == '會考' and result['metadata']['cap_difficulty_level'] == level
    assert set(result) >= {'metadata', 'instructions', 'sections'}
    errors = check(result)
    if key != '會考寫作測驗':
        assert any('target_counts' in e for e in errors)   # the author fills the four-band counts first
        slots = [s for s in result['planning_slots'] if s['type'] == 'single_choice']
        assert len(slots) == {'會考國文': 42, '會考英語': 43, '會考數學': 25, '會考社會': 54, '會考自然': 50}[key]
        if level == '極難':
            assert all(s['target_p'] < s['official_p_113_115'][0] for s in slots[:5])
        skeleton = item(key, 1, level)
        assert skeleton['question']['options'][0] == {'label': 'A', 'text': None}
        assert len(skeleton['answer']['reasoning']) == (3 if level == '極難' else 2)
    if key == '會考社會':
        domains = [s['domain'] for s in slots if 'domain' in s]
        runs, longest, switches = 1, 1, 0
        for a, b in zip(domains, domains[1:]):
            runs = runs + 1 if a == b else 1
            longest, switches = max(longest, runs), switches + (a != b)
        assert longest <= MAX_RUN and switches >= MIN_SWITCHES
        assert all(0.25 <= domains.count(d) / len(domains) <= 0.42 for d in ('歷史', '地理', '公民'))


def test_cap_solutions_print_codes_and_likely_volume(tmp_path):
    from cap_plan import textbook_volumes
    exam = cap_paper('會考社會', tmp_path)
    exam['questions'][0]['item_spec']['curriculum_codes'] = ['歷Ha-IV-1', '地Ab-IV-2']
    _, solutions = workflow.project_specs(exam, {}, 459.7)
    first = next(b for b in solutions['blocks'] if b.get('kind') == 'solution')
    assert first['steps'][0] == '課綱：歷Ha-IV-1、地Ab-IV-2；可能出處：第三冊（八上）'
    assert textbook_volumes({'curriculum_codes': ['N-8-1', 'S-9-2']}) == ['第三、四冊（八年級）', '第五、六冊（九年級）']
    del exam['questions'][1]['item_spec']['textbook_volumes']
    from validate_cap_quality import validate_items
    assert any('textbook_volumes' in e for e in validate_items(exam))


def test_auto_review_executes_the_mechanical_paper_checks(tmp_path):
    from hosted_auto_review import auto_review
    exam = cap_paper('會考社會', tmp_path)
    exam['metadata'].update(paper_id='auto', generation_mode='full-paper')
    (tmp_path / 'exam.json').write_text(json.dumps(exam, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'run-state.json').write_text(json.dumps({'subject': '會考社會', 'pdfs': {}}), encoding='utf-8')
    result = auto_review(tmp_path / 'run-state.json')
    reviews = {g: json.loads((tmp_path / f'{g}.json').read_text(encoding='utf-8')) for g in result['reviews']}
    assert reviews['template_composition']['status'] == 'pending'          # nothing built yet
    assert 'build both booklets' in reviews['template_composition']['observations']
    assert reviews['structure_scope']['observations'].startswith('executed hosted_subject_gates')
    assert all(r['exam_sha256'] == hashlib.sha256((tmp_path / 'exam.json').read_bytes()).hexdigest()
               for r in reviews.values())


def test_cap_photos_are_mostly_new_when_the_web_is_reachable(tmp_path):
    from validate_cap_quality import validate_items
    from web_image import candidates
    exam = cap_paper('會考社會', tmp_path)
    for n, q in enumerate(exam['questions'][:5]):
        q['visual_asset'] = {'path': f'p{n}.jpg', 'sha256': f'h{n}',
                             'visual_spec': {'kind': 'photo', 'generation_mode': 'photo_library' if n < 3 else 'web_source'}}
    (tmp_path / 'preflight.json').write_text(json.dumps({'image_sources': {'web_images': 'reachable'}}), encoding='utf-8')
    assert any('newly found' in e for e in validate_items(exam, asset_root=tmp_path))
    (tmp_path / 'preflight.json').write_text(json.dumps({'image_sources': {'web_images': 'unreachable'}}), encoding='utf-8')
    assert not any('newly found' in e for e in validate_items(exam, asset_root=tmp_path))
    # Commons search rows: rasters only, bundled-library pages flagged and listed last.
    payload = {'query': {'pages': {
        '1': {'title': 'File:Map of Kanan Irrigation System.jpg', 'imageinfo': [{'mime': 'image/jpeg', 'width': 3332,
              'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Map_of_Kanan_Irrigation_System.jpg',
              'extmetadata': {'LicenseShortName': {'value': 'Public domain'}}}]},
        '2': {'title': 'File:New gate.jpg', 'imageinfo': [{'mime': 'image/jpeg', 'width': 900,
              'descriptionurl': 'https://commons.wikimedia.org/wiki/File:New_gate.jpg',
              'extmetadata': {'Artist': {'value': '<a>Someone</a>'}, 'DateTimeOriginal': {'value': '1938date QS:P,+1938'}}}]},
        '3': {'title': 'File:Diagram.svg', 'imageinfo': [{'mime': 'image/svg+xml'}]}}}}
    rows = candidates(payload)
    assert [r['title'] for r in rows] == ['File:New gate.jpg', 'File:Map of Kanan Irrigation System.jpg']
    assert rows[0]['creator'] == 'Someone' and rows[0]['date'] == '1938' and rows[1]['in_bundled_library']


def test_advance_stops_where_the_author_must_act(tmp_path):
    exam = cap_paper('會考社會', tmp_path)
    exam['metadata'].update(paper_id='adv', generation_mode='full-paper')
    exam['questions'] = exam['questions'][:10]
    (tmp_path / 'exam.json').write_text(json.dumps(exam, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'run-state.json').write_text(json.dumps({'paper_id': 'adv', 'subject': '會考社會', 'checks': {}}),
                                             encoding='utf-8')
    result = workflow.advance(tmp_path / 'run-state.json')
    assert result['status'] == 'pending' and result['stopped_at'] == 'authoring'
    assert '10 of 54' in result['todo'] and (tmp_path / 'NEXT.md').is_file()


def test_cap_gates_from_the_115_comparison(tmp_path):
    """Combination items, figure options, long options, unsourced statistics, running difficulty, overlap."""
    from validate_cap_quality import official_overlaps, validate_items
    exam = cap_paper('會考社會', tmp_path)
    for q in exam['questions'][:6]:
        for i, c in enumerate('ABCD'):
            q['options'][i]['text'] = ['甲乙', '甲丙', '乙丁', '丙丁'][i]
    for q in exam['questions'][20:40]:
        for o in q['options']:
            o['text'] = o['text'] + '這是一個刻意寫得很長很長的選項敘述內容'
    exam['questions'][30]['prompt'] = '2024年該地出生數為13萬4,856人，較前一年減少約1萬人，下列推論何者正確？'
    for x in exam['questions'][:40]:
        x['item_spec']['difficulty_design']['estimated_p'] = 0.92
    for q in exam['questions']:
        if q['options'][0]['text'].startswith('{{asset:'):
            for i, o in enumerate(q['options']):
                o['text'] = f'圖形選項改回文字{i}'
    errors = validate_items(exam, asset_root=tmp_path)
    for needle in ('甲乙丙丁 combinations', 'figures as options', 'options run long', 'prints real-world data', 'running mean'):
        assert any(needle in e for e in errors), (needle, [e for e in errors if 'Q' not in e[:3]])
    # A shared curriculum term is not a rewrite; several shared phrases of one official item are.
    assert official_overlaps('日本統治時期的水庫蓄水量與法定代理人') == []
    assert official_overlaps('日治時期，臺灣製糖會社在原料採取區域內收購甘蔗，蔗農只能把甘蔗賣給區域內的製糖會社，價格由會社決定。')


def test_cap_option_columns_fit_the_13pt_body():
    q = lambda texts, **extra: {'options': [{'label': c, 'text': t} for c, t in zip('ABCD', texts)], **extra}
    assert workflow.option_columns(q(['十三個字的選項文字剛好十三'] * 4), '會考社會') == 2
    assert workflow.option_columns(q(['十五個字的選項文字會折行放不下'] * 4), '會考社會') == 1
    assert workflow.option_columns(q(['短'] * 4), '會考社會') == 4
    assert workflow.option_columns(q(['十五個字的選項文字會折行放不下'] * 4, option_layout='grid-2'), '會考社會') == 2
    assert workflow.option_columns(q(['{{asset:a}}', '{{asset:b}}', '{{asset:c}}', '{{asset:d}}']), '會考自然') == 2


def test_compact_records_expand_to_a_savable_batch(tmp_path):
    from cap_plan import expand, plan
    from hosted_subject_gates import answer_explanation_errors
    for c in 'ABCD':
        (tmp_path / f'm{c}.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="110"/>', encoding='utf-8')
    base = dict(codes=['地Ab-IV-1'], volumes=['第一冊'], context_type='生活情境', process='推論', anchor='佔位', evidence='佔位',
                prerequisites=['佔位'], hidden_concept='佔位目標', band='中', est_p=0.62, est_d=0.5, decisions=['一', '二'],
                short_route='佔位', misconception='佔位', bottleneck=['佔位'], minutes=1.2)
    dis = {c: {'misconception': '佔位', 'peer_concept': '佔位', 'pick': 0.12, 'ruled_out_by': '佔位'} for c in 'ACD'}
    rows = [dict(base, number=1, stem='佔位？', images=[f'm{c}.svg' for c in 'ABCD'], key='B', distractors=dis,
                 steps=['一。', '故選(B)；(A)(C)(D)不符。']),
            dict(base, number=44, material='題組材料。', stem='佔位？', options=['佔位甲', '佔位乙', '佔位丙', '佔位丁'], key='B',
                 distractors=dis, steps=['一。', '佔位乙符合，故選(B)；(A)(C)(D)不符。']),
            dict(base, number=45, material='題組材料。', stem='佔位？', options=['佔位甲', '佔位乙', '佔位丙', '佔位丁'], key='B',
                 distractors=dis, steps=['一。', '佔位乙符合，故選(B)；(A)(C)(D)不符。'])]
    batch = expand(plan('會考社會', 'x', seed='s'), rows, tmp_path)
    q1, q44, q45 = batch['questions']
    assert q1['options'][1]['text'] == '{{asset:q1B}}' and q1['inline_assets']['q1B']['sha256']
    assert q44['section_id'] == 's2' and q45['item_spec']['inherits_audit_from'] == 'q44'
    assert q1['item_spec']['difficulty_design']['content_sha256'] and batch['answers'][0]['final_answer'] == 'B'
    assert set(q1['item_spec']['cap_distractors']) == {'A', 'C', 'D'}
    exam = {'metadata': {'subject': '會考社會'}, **batch}
    assert answer_explanation_errors(exam) == []
