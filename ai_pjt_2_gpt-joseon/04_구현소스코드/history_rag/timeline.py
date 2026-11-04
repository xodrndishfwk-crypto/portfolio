"""공식 실록 목차의 왕력/서기년을 그대로 사용. 즉위년을 계산해 만들지 않는다."""
import json
import re
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup
from .settings import ROOT


def parse_periods(html, collection, book_id):
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for row in soup.select('tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) < 4:
            continue
        anchor = cells[0].find('a', href=True)
        label = cells[0].get_text(' ', strip=True)
        year = cells[2].get_text(strip=True)
        if not anchor or not year.isdigit() or not 1392 <= int(year) <= 1910:
            continue
        href = anchor['href'].lstrip('#')
        node_id = parse_qs(urlparse(href).query).get('dataId', [''])[0]
        match = re.fullmatch(r'(.+?)\s+(즉위년|\d+년)', label)
        if not node_id or not match:
            continue
        months = []
        for a in cells[3].find_all('a'):
            m = re.search(r'dataId=([A-Za-z0-9_]+)', a.get('onclick', '') + a.get('href', ''))
            if m:
                months.append({'label': a.get_text(' ', strip=True), 'id': m.group(1)})
        result.append({'id': node_id, 'item_kind': 'royal_year', 'title': label, 'king': match[1],
                       'reign_label': match[2], 'year': int(year), 'collection': collection, 'book_id': book_id,
                       'date_original': f'{label} ({year})', 'date_precision': 'year', 'date_converted': False,
                       'era_original': cells[1].get_text(' ', strip=True), 'months': months,
                       'url': f'https://db.itkc.or.kr/dir/node?dataId={node_id}',
                       'service': '한국고전종합DB 공식 목차', 'source_kind': '항목 메타데이터',
                       'rights_status': 'permitted', 'rights_basis': '공식 목차에서 추출한 왕력·연도·식별자 사실 관계를 자체 구조화',
                       'snippet': f'{label}, 서기 {year}년에 해당하는 기록 탐색 항목. 사건 본문이 아닌 연도 색인이다.',
                       'validation': 'catalogue_verified', 'body_status': 'not_collected'})
    return result


def load_periods():
    path = ROOT / 'resources' / 'royal_years.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def match_periods(periods, question='', king=None, year=None):
    """LLM의 왕/연도는 검색 단서이며 날짜의 사실 근거가 아니다."""
    explicit_years = [int(y) for y in re.findall(r'(?<!\d)(1[3-9]\d{2})(?:년)?', question)]
    found_king = next((k for k in sorted({p['king'] for p in periods}, key=len, reverse=True) if k in question), None)
    king = found_king or king
    year = explicit_years[0] if explicit_years else year
    matched = [p for p in periods if (not king or p['king'] == king) and (not year or p['year'] == year)]
    if king:
        reign = re.search(re.escape(king) + r'\s*(즉위년|\d+년)', question)
        if reign:
            matched = [p for p in matched if p['reign_label'] == reign.group(1)]
    return matched if (king or year) else []
