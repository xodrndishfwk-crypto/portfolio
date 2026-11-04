"""검증한 왕력 표로 답할 수 있는 좁은 연도/왕대 질문. 사건 지식으로 확대하지 않는다."""
import re
from langchain_core.documents import Document
from .timeline import match_periods


def chronology_periods(question, history, periods):
    if not re.search(r'어느\s*왕|어떤\s*왕|무슨\s*왕|왕대|누구\s*때|왕.*재위|몇\s*년|몇년도|(?:누가|누구|어느\s*임금).{0,12}(?:다스|통치|재위|임금|왕)|(?:왕|임금|다스리던).{0,12}(?:누구|누가)|누가.{0,8}(?:때|시기)', question):
        return []
    if re.search(r'왜|배경|원인|죽|전쟁|사건|어떻게|\d+\s*[월일]', question):
        return []
    years = re.findall(r'(?<!\d)(1[3-9]\d{2})(?:년)?', question)
    if not years:
        direct = match_periods(periods, question)
        if len(direct) == 1:
            return direct
        if any(p['king'] in question for p in periods):
            return []
        # 짧은 후속 질문에서는 가장 최근 답변의 유일한 연도만 맥락으로 사용한다.
        prior = next((m.get('content', '') for m in reversed(history) if m.get('role') == 'assistant'), '')
        years = re.findall(r'(?<!\d)(1[3-9]\d{2})(?:년)?', prior)
        if not years:
            prior_periods = match_periods(periods, prior)
            if len(prior_periods) == 1:
                return prior_periods
    years = set(map(int, years))
    if len(years) != 1:
        return []
    return [p for p in periods if p['year'] in years]


def chronology_evidence(periods):
    docs = []
    for p in periods:
        text = f"서기 {p['year']}년은 {p['title']}에 해당한다. 왕은 {p['king']}이다.\n공식 왕력 목차에서 확인한 연도 대응이며 사건 내용의 근거는 아니다."
        docs.append(Document(page_content=text, metadata={
            'article_id': p['id'] + ':chronology', 'title': p['title'] + ' · 서기년 대조',
            'url': p['url'], 'source_kind': '왕력 대조', 'is_primary': False,
            'collection': p.get('collection', ''), 'date': str(p['year']),
            'service': p.get('service', '왕력 연도표'), 'derivation': '왕력 메타데이터의 명시적 연도/왕 관계만 대조'}))
    return docs


def subject_particle(name):
    code = ord(name[-1]) - 0xAC00 if name else -1
    return '이' if 0 <= code <= 11171 and code % 28 else '가'


def chronology_answer(periods, docs):
    year = periods[0]['year']
    if len(periods) == 1:
        p = periods[0]
        text = f"{year}년은 {p['title']}이란다. {p['king']}{subject_particle(p['king'])} 다스리던 시기야."
    else:
        text = f"{year}년에는 " + '과 '.join(p['title'] for p in periods) + "이 함께 해당한단다. 왕이 바뀐 해라 정확한 왕대는 그해의 날짜를 함께 봐야 해."
    entries = [{'number': i, 'quote': d.page_content.split('\n')[0]} for i, d in enumerate(docs, 1)]
    claim = f'{year}년의 왕력 연도 대응'
    return {'response': {'text': text, 'evidence': entries}, 'interpretation': {'text': '', 'evidence': []},
        'aside': {'text': '', 'evidence': []}, 'ai_translation': {'text': '', 'evidence': []},
        'claims': [{'claim': claim, 'verdict': '기록상 뒷받침됨', 'explanation': text, 'evidence': entries}],
        'unknowns': [], 'follow_up_questions': [], 'has_primary_evidence': False,
        'source_types': ['왕력 대조'], 'evidence_scope': '왕력 표로 확인한 연도 대응',
        'style_version': 'teacher-v3', 'summary': '기록상 뒷받침됨'}
