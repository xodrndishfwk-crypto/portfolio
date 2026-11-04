import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from history_rag.settings import settings, ROOT
from history_rag.sources import SourceClient
from history_rag.storage import Store
from history_rag.timeline import parse_periods


def main():
    store = Store()
    source = SourceClient(store, settings())
    html = source.get('https://db.itkc.or.kr/dir/list', {'itemId': 'JT', 'gubun': 'book', 'pageUnit': 100})
    books = []
    for a in BeautifulSoup(html, 'html.parser').select('td > a[href]'):
        if not a['href'].startswith('#/dir/node?'):
            continue
        m = re.search(r'dataId=(ITKC_JT_[A-Z]0)$', a['href'])
        if m:
            books.append((m.group(1), a.get_text(' ', strip=True)))
    result = []
    for book_id, collection in dict(books).items():
        key = 'catalogue:' + book_id
        cache = store.cache_get(key, 30 * 86400)
        rows = cache['data'] if cache and cache['status'] == 'ok' else parse_periods(source.get('https://db.itkc.or.kr/dir/node', {'dataId': book_id}), collection, book_id)
        if not rows:
            raise RuntimeError('연도 목차를 확인하지 못했습니다: ' + book_id)
        for row in rows:
            row['collection'] = collection
        store.cache_put(key, 'ok', rows)
        result.extend(rows)
        print(collection, len(rows), flush=True)
    # ITKC 목차는 태조~철종 25왕대만 노드 제공. 고종·순종은 국편의
    # 즉위년/마지막 재위년 표기 확인 후 별도 출처·내부 ID로 구성한다.
    for king, start, end, source_url in [
        ('고종', 1863, 1907, 'https://sillok.history.go.kr/intro/haejae.do'),
        ('순종', 1907, 1910, 'https://sillok.history.go.kr/id/kzb_10007019_001')]:
        for year in range(start, end + 1):
            label = '즉위년' if year == start else f'{year-start}년'
            result.append({'id': f'period:{king}:{year}', 'item_kind': 'royal_year', 'title': f'{king} {label}',
                           'king': king, 'year': year, 'reign_label': label, 'collection': king + '실록',
                           'book_id': '', 'date_original': f'{king} {label} ({year})', 'date_precision': 'year',
                           'date_converted': False, 'era_original': '', 'months': [], 'url': source_url,
                           'service': '국사편찬위원회 왕대·왕력 표기 기반 연도표', 'source_kind': '항목 메타데이터',
                           'rights_status': 'permitted', 'rights_basis': '공식 자료에서 확인한 왕력 연도 사실 관계를 자체 구성',
                           'snippet': f'{king} {label}, 서기 {year}년. 사건 본문이 아닌 연도 탐색 항목.',
                           'validation': 'chronology_rule', 'body_status': 'not_collected'})
    if len({p['king'] for p in result}) != 27 or len(result) < 500:
        raise RuntimeError('27개 왕대 또는 500개 이상의 실제 연도 목차를 확보하지 못했습니다.')
    for p in result:
        store.put_period(p)
    target = ROOT / 'resources'
    target.mkdir(exist_ok=True)
    (target / 'royal_years.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {'periods': len(result), 'kings': len({p['king'] for p in result}), 'unique_ce_years': len({p['year'] for p in result}),
              'catalogue_verified': sum(p['validation'] == 'catalogue_verified' for p in result),
              'chronology_rule': sum(p['validation'] == 'chronology_rule' for p in result),
              'min_year': min(p['year'] for p in result), 'max_year': max(p['year'] for p in result),
              'source': 'https://db.itkc.or.kr/dir/list?itemId=JT&gubun=book&pageUnit=100', 'method': '태조~철종 공식 목차 + 국편 왕력 기준 고종/순종 자체 연도표. 수정/개수 판본 중복 제외'}
    (ROOT / 'docs' / 'timeline_status.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
