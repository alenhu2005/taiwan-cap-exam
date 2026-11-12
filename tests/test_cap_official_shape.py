"""會考: the official 113-115 shape of each paper (units, forms, numbering, layout) and the review tools.

Synthetic fixtures only: placeholder wording, never exam questions.
"""
import json
from pathlib import Path
import sys

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import cap_plan
import cap_units
import run_hosted_workflow as workflow
from append_items import merge_plan
from hosted_body_templates import render
from hosted_density import booklet_limits
from validate_cap_quality import math_form_errors, numeric_values, option_order_errors, real_data, validate_items
from validate_math_context import source_note_samples
from test_cap_pipeline import cap_paper, font  # noqa: F401  (fixture)


def test_math_plan_keeps_the_group_in_part_one_and_numbers_the_constructed_items_after_it():
    plan = cap_plan.plan('會考數學', 'p', seed='s')
    slots = {(s['number'], s['type']): s for s in plan['planning_slots']}
    assert all(slots[(n, 'single_choice')]['section_id'] == 's1' for n in (23, 24, 25))
    c1, c2 = slots[(26, 'constructed_response')], slots[(27, 'constructed_response')]
    assert (c1['section_id'], c1['number_display'], c1['answer_label']) == ('s2', '1.', '非選擇題第1題')
    assert c2['number_display'] == '2.'
    assert type(plan['metadata']['difficulty_balance_plan']['shared_reading_minutes']) is int
    batch = cap_plan.expand(plan, [{'number': 1, 'constructed': True, 'stem': '合成', 'answer': '見詳解',
                                    'steps': ['一', '二', '三'], 'rubric': {'3': '完整'}}], ROOT)
    assert (batch['questions'][0]['id'], batch['questions'][0]['number']) == ('c1', 26)


@pytest.mark.parametrize('subject', ['會考數學', '會考國文', '會考英語', '會考自然'])
def test_plans_schedule_units_inside_the_official_ranges(subject):
    for seed in ('a', 'b', 'c'):
        slots = cap_plan.plan(subject, 'p', seed=seed)['planning_slots']
        choice = [s for s in slots if s['type'] == 'single_choice']
        items = [{'type': 'single_choice', 'number': s['number'],
                  'item_spec': {'cap_unit': s.get('unit'), 'cap_competency': {'domain': s.get('domain')}}} for s in choice]
        assert cap_units.unit_errors(subject, items, volumes=False) == []
        if subject == '會考自然':
            volumes = [s['suggested_volume'] for s in choice]
            assert all(volumes.count(v) >= 3 for v in cap_units.VOLUME_NAMES)
        if subject == '會考英語':
            assert {s['unit'] for s in choice if s['number'] >= 40} == {'克漏字'}
        if subject == '會考數學':
            assert all(s['suggested_form'].startswith('直接作答') for s in choice if s['number'] <= 3)
            late = [s['number'] for s in choice if s['unit'] in ('圓', '相似形與三角形三心')]
            assert min(late) >= 8   # circles and similar triangles close the paper, as 113-115 print them


def test_unit_coverage_rejects_the_m1111_shape():
    units = (['統計'] * 3 + ['機率'] * 2 + ['數與運算'] * 7 + ['方程式與不等式'] * 5 + ['平面幾何'] * 5 +
             ['坐標與函數'] * 2 + ['數列'])
    items = [{'type': 'single_choice', 'number': n, 'item_spec': {'cap_unit': u}} for n, u in enumerate(units, 1)]
    errors = ' '.join(cap_units.unit_errors('會考數學', items))
    for unit in ('圓', '相似形與三角形三心', '二次方根', '多項式與一元二次方程式', '統計＋機率'):
        assert unit in errors


def test_math_form_rules(tmp_path):
    exam = cap_paper('會考數學', tmp_path)
    assert math_form_errors(exam) == [] and option_order_errors(exam) == []
    q = exam['questions'][8]
    for o, t in zip(q['options'], ['40', '4', '30', '50']):
        o['text'] = t
    assert option_order_errors(exam) and numeric_values(['4', '30', '40', '50']) == [4, 30, 40, 50]
    assert numeric_values(['7/12', '5/12', '1/3', '5/7']) is None   # fractions are ordered by form
    exam['questions'][0]['item_spec']['cap_competency']['context_type'] = '生活情境'
    stories = ['一把梯子斜靠在牆上，梯腳向外滑動。', '靠著牆用圍籬圍出長方形菜圃。', '彈力球從高處落下後反彈。']
    for q, story in zip(exam['questions'][10:13], stories):
        q['prompt'] = story
    errors = ' '.join(math_form_errors(exam))
    assert 'open with three direct items' in errors and 'textbook exercise' in errors
    for q in exam['questions'][:25]:
        for o, t in zip(q['options'], ['1', '2', '3', '4']):
            o['text'] = t
    assert 'other than a bare number' in ' '.join(math_form_errors(exam))


def test_expand_sorts_numeric_options_and_moves_the_key_and_the_steps():
    plan = cap_plan.plan('會考數學', 'p', seed='s')
    row = {'number': 9, 'stem': '合成', 'options': ['40', '4', '30', '50'], 'key': 'D',
           'distractors': {c: {'misconception': c} for c in 'ABC'}, 'steps': ['故選(D)。(A)錯，選項B錯，C選項錯。']}
    batch = cap_plan.expand(plan, [row], ROOT)
    assert [o['text'] for o in batch['questions'][0]['options']] == ['4', '30', '40', '50']
    assert batch['answers'][0]['final_answer'] == 'D'
    assert batch['answers'][0]['reasoning'] == ['故選(D)。(C)錯，選項A錯，B選項錯。']
    assert sorted(batch['questions'][0]['item_spec']['cap_distractors']) == ['A', 'B', 'C']


def test_only_claimed_real_data_needs_a_source_outside_social():
    assert not real_data('會考自然', '某生測得水溫 25 ℃，加熱 3 分鐘後升高 12 ℃。')
    assert not real_data('會考數學', '某國政府公布 2023 年的全國用電量為 2700 億度。')
    assert real_data('會考數學', '根據內政部統計，2024 年出生數為 13 萬人。')
    assert real_data('會考社會', '該地人口 13 萬人。')


def test_the_solution_volume_note_is_not_a_source_note():
    assert source_note_samples('課綱：N-8-1；可能出處：第三、四冊（八年級）') == []
    assert source_note_samples('資料出處：某網站') and source_note_samples('出處：某書')


def test_fraction_options_print_four_abreast_and_point_names_italic(font, tmp_path):
    exam = {'metadata': {'exam': '會考', 'subject': '會考數學'},
            'sections': [{'id': 's1', 'title': '第一部分：選擇題（1～25題）'}],
            'questions': [{'id': 'q1', 'number': 1, 'section_id': 's1', 'type': 'single_choice',
                           'prompt': '△ABC 旋轉後 C′ 在 BC 上，長方形 ABCD 與正六邊形 ABCDEF，Y 字型沙發。',
                           'options': [{'label': c, 'text': t} for c, t in zip('ABCD', ['7/12', '5/12', '1/3', '5/7'])]}],
            'answers': [{'question_id': 'q1', 'final_answer': 'A', 'reasoning': ['一', '二']}]}
    spec, _ = workflow.project_specs(exam, {}, 460)
    render(spec, tmp_path / 'b.pdf', tmp_path / 'b.json', font, asset_root=tmp_path)
    with pymupdf.open(tmp_path / 'b.pdf') as doc:
        words = doc[0].get_text('words')
        spans = [s for b in doc[0].get_text('dict')['blocks'] for line in b.get('lines', []) for s in line['spans']]
    labels = sorted((w[1], w[0]) for w in words if w[4] in ('(A)', '(B)', '(C)', '(D)'))
    assert len({round(y) for y, _ in labels}) == 1   # one row
    italic = {s['text'].strip() for s in spans if 'Italic' in s['font']}
    assert {'ABCD', 'ABCDEF', 'BC'} <= italic and 'Y' not in italic
    assert '∆' in doc_text(tmp_path / 'b.pdf') and '△' not in doc_text(tmp_path / 'b.pdf')


def doc_text(path):
    with pymupdf.open(path) as doc:
        return ''.join(p.get_text() for p in doc)


def test_each_constructed_item_opens_its_own_working_page(font, tmp_path):
    exam = cap_paper('會考數學', tmp_path)
    exam['sections'][1]['title'] = '第二部分：非選擇題（1～2題）'
    spec, _ = workflow.project_specs(exam, {}, 460)
    layout = render(spec, tmp_path / 'q.pdf', tmp_path / 'q.json', font, asset_root=tmp_path)
    pages = {p['id']: p['page'] for p in layout['parts']}
    assert pages['c2'] == pages['c1'] + 1 and pages['c1'] > pages['q25']
    assert layout['working_pages'] == [pages['c1'], pages['c2']]
    texts = [(n, t) for n, t in enumerate(['請不要翻到次頁！', '1. 合成', '第二部分：非選擇題 1.', '2. 合成', '參考公式：'], 1)]
    limits = booklet_limits(texts, '會考數學')
    assert limits[3] == ('working', None) and limits[4] == ('working', None) and limits[2][1] is not None


def test_a_later_plan_updates_the_saved_metadata():
    exam = {'metadata': {'paper_id': 'p', 'subject': '會考數學', 'title': 'old',
                         'difficulty_balance_plan': {'target_counts': {}}},
            'instructions': [], 'sections': [{'id': 's1'}], 'questions': [{'id': 'q1', 'section_id': 's1'}]}
    plan = {'metadata': {'paper_id': 'p', 'subject': '會考數學', 'title': 'new',
                         'difficulty_balance_plan': {'target_counts': {'簡單': 5}}},
            'instructions': [], 'sections': [{'id': 's1'}, {'id': 's2'}]}
    assert set(merge_plan(exam, plan)) == {'metadata.title', 'metadata.difficulty_balance_plan', 'sections'}
    assert exam['metadata']['difficulty_balance_plan']['target_counts'] == {'簡單': 5}
    with pytest.raises(ValueError):
        merge_plan(exam, {'metadata': {'paper_id': 'other'}})
    with pytest.raises(ValueError):
        merge_plan(exam, {'metadata': {}, 'sections': [{'id': 's2'}]})


def test_auto_review_writes_a_difficulty_draft_with_the_right_anchor_keys(tmp_path):
    from hosted_auto_review import difficulty_draft
    exam = cap_paper('會考數學', tmp_path)
    (tmp_path / 'exam.json').write_text(json.dumps(exam, ensure_ascii=False), encoding='utf-8')
    draft = json.loads(difficulty_draft(exam, tmp_path).read_text(encoding='utf-8'))
    keys = {row['id']: row['anchor']['key'] for row in draft['items']}
    assert keys['q1'] == 'objective' and keys['c1'] == 'constructed-response'
    assert all(row['status'] == 'pending' and 'observations' in row for row in draft['items'])
    assert (tmp_path / draft['blind_packet']['path']).is_file()


def test_difficulty_review_accepts_official_low_d_and_doubts_inflated_hard_items():
    from hosted_blind_review import CAP_HARD_D_MEAN, CAP_LOW_D_SHARE_BY_SUBJECT
    assert CAP_LOW_D_SHARE_BY_SUBJECT['會考數學'] * 25 >= 2   # official 115 數學: 2 of 25 below 0.30
    assert 0.30 <= CAP_HARD_D_MEAN['會考數學'] <= 0.40


def test_cap_draw_prints_math_glyphs_in_the_booklet_faces(tmp_path):
    from cap_draw import draw
    spec = {'width_pt': 200, 'view': [-1, 9, -3, 7], 'items': [
        {'grid': {'step': 1}}, {'axes': {'ticks': 2}}, {'polygon': [[0, 0], [8, 6], [6, -2]]},
        {'point': [8, 6], 'label': 'A′'}, {'right_angle': [[0, 0], [8, 6], [6, -2]]}, {'text': '−3…', 'at': [4, 6]}]}
    result = draw(spec, tmp_path / 'f.pdf')
    with pymupdf.open(tmp_path / 'f.pdf') as doc:
        text = doc[0].get_text()
        fonts = {f[3] for f in doc[0].get_fonts()}
    assert 'A′' in text and '−3…' in text and '−2' in text and '·' not in text
    assert any('Italic' in f for f in fonts) and result['height_pt'] > 0


def test_the_formula_page_stays_inside_its_box():
    path = ROOT / 'exam_packs/會考/templates/115/assets/cap-math/formula-blank.pdf'
    with pymupdf.open(path) as doc:
        page = doc[0]
        box = max((d['rect'] for d in page.get_drawings() if d.get('rect') is not None), key=lambda r: r.width)
        spans = [s for b in page.get_text('dict')['blocks'] for line in b.get('lines', []) for s in line['spans']
                 if s['text'].strip() and s['bbox'][1] > box.y0]
    assert spans and all(s['bbox'][2] <= box.x1 for s in spans)


def test_the_writing_task_follows_the_official_frame(tmp_path):
    from validate_cap_form import validate_exam
    exam = cap_paper('會考寫作測驗', tmp_path)
    assert validate_exam(exam) == []
    task = exam['questions'][0]
    task['prompt'] = task['prompt'].replace('※不可使用詩歌體', '').replace('請先閱讀', '題目：請閱讀')
    exam['answers'][0]['reasoning'] = ['合成評閱說明。']
    errors = ' '.join(validate_exam(exam))
    for needle in ('opens', 'three notes', 'no title', '立意取材'):
        assert needle in errors
    assert cap_plan.plan('會考寫作測驗', 'p', seed='s')['metadata']['writing_frame']['notes'][0] == '※不必訂題'


def test_solutions_print_estimated_difficulty_and_discrimination(tmp_path):
    exam = cap_paper('會考數學', tmp_path)
    exam['questions'][0]['item_spec']['difficulty_design'].update(estimated_p=0.62, estimated_d=0.45)
    _, solutions = workflow.project_specs(exam, {}, 460)
    blocks = {b['id']: b for b in solutions['blocks'] if b.get('kind') == 'solution'}
    assert blocks['q1']['steps'][1] == '難易度：中（預估通過率 0.62）；鑑別度：優良（預估 0.45）'
    # A registered difficulty review overrides the author's estimates.
    _, solutions = workflow.project_specs(exam, {}, 460, {'q1': {'estimated_p': 0.35, 'estimated_d': 0.25}})
    first = next(b for b in solutions['blocks'] if b.get('id') == 'q1')
    assert first['steps'][1] == '難易度：難（預估通過率 0.35）；鑑別度：尚可（預估 0.25）'
    assert cap_plan.difficulty_note({}) == ''


def test_science_and_english_habits_from_the_item_analysis(tmp_path):
    from validate_cap_quality import subject_habit_errors
    science = cap_paper('會考自然', tmp_path)
    assert subject_habit_errors(science) == [] and cap_units.unit_errors('會考自然', science['questions']) == []
    for q in science['questions']:
        q['item_spec']['textbook_volumes'] = ['第四冊']
        q['item_spec']['cap_competency'].update(context_type='生活情境', process='推論')
    for q in science['questions'][:4]:
        q['prompt'] = '下列何者最不可能發生？'
    errors = ' '.join(subject_habit_errors(science) + cap_units.unit_errors('會考自然', science['questions']))
    for needle in ('experiments or investigations', 'ask in the negative', 'teach from 第一冊'):
        assert needle in errors
    english = cap_paper('會考英語', tmp_path)
    assert subject_habit_errors(english) == []
    english['questions'][0].pop('visual_asset')
    assert 'picture item' in ' '.join(subject_habit_errors(english))


def test_plans_give_structure_types_for_every_subject():
    science = cap_plan.plan('會考自然', 'p', seed='s')['planning_slots']
    assert all(s.get('suggested_form') for s in science if s['type'] == 'single_choice')
    chinese = cap_plan.plan('會考國文', 'p', seed='s')['planning_slots']
    forms = {s['suggested_form'] for s in chinese if s.get('unit') == '語文知識'}
    assert set(cap_plan.CHINESE_KNOWLEDGE_FORMS[:5]) <= forms
    english = cap_plan.plan('會考英語', 'p', seed='s')['planning_slots']
    assert english[0]['suggested_form'].startswith('看圖作答')
    assert all(s.get('suggested_form') for s in english if s.get('group') and s.get('unit') != '克漏字')
    assert cap_plan.plan('會考數學', 'p', seed='s')['subject_guide'] == 'references/cap-math.md'


def test_each_subject_reads_only_its_own_guide():
    from read_web_knowledge import SUBJECT_REFERENCES
    guides = {'會考國文': 'cap-chinese.md', '會考英語': 'cap-english.md', '會考數學': 'cap-math.md',
              '會考社會': 'cap-social.md', '會考自然': 'cap-science.md', '會考寫作測驗': 'cap-writing.md'}
    for subject, guide in guides.items():
        assert guide in SUBJECT_REFERENCES[subject]
        assert not (set(guides.values()) - {guide}) & SUBJECT_REFERENCES[subject]
        assert (ROOT / 'references' / guide).is_file()
