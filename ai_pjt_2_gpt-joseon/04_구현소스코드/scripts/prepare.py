"""공개 검색 API 메타데이터 확보. 본문은 이용 조건 검증 이후 별도 실행."""
import argparse
import json
from collections import Counter
from history_rag.settings import settings, ROOT
from history_rag.storage import Store
from history_rag.sources import SourceClient

TERMS = ['간쟁', '무고', '소문', '감형', '처벌', '사관', '상소', '국문', '노비', '억울']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bodies', action='store_true')
    parser.add_argument('--index', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--limit', type=int, default=120)
    args = parser.parse_args()
    config, store = settings(), Store()
    client = SourceClient(store, config)
    errors = []
    if not args.index and not args.bodies:
        # 앞쪽에 편중되지 않게 검색어와 서로 다른 결과 위치를 사용한다.
        for term in TERMS:
            for offset in [0, 120, 600]:
                try:
                    records = client.search(term, start=offset, rows=5, refresh=args.refresh)
                    for a in records:
                        current = store.get(a['id'])
                        current['discovery_query'] = term
                        current['discovery_offset'] = offset
                        store.put(current)
                    print(json.dumps({'query': term, 'offset': offset, 'received': len(records)}, ensure_ascii=False), flush=True)
                except Exception:
                    errors.append({'query': term, 'offset': offset, 'status': 'request_failed'})
    if args.bodies:
        if not config['allow_body_storage']:
            raise SystemExit('본문 저장 이용 조건 미확인: docs/sources.md 참조. 대량 수집 보류.')
        for a in store.articles()[:args.limit]:
            try:
                result = client.fetch(a, refresh=args.refresh)
                print(result['id'], result['validation'], flush=True)
            except Exception:
                errors.append({'id': a['id'], 'status': 'body_failed'})
    if args.index:
        from history_rag.index import Index
        from history_rag.llm import embeddings
        index = Index(embeddings(config), config)
        print('new metadata chunks', index.index_metadata(store.articles()))
        for a in store.articles():
            if a.get('validation') == 'valid':
                index.index_body(a['id'], a)
        print(index.counts())
    report = {**store.counts(), 'king_distribution': dict(Counter(a.get('king', '') for a in store.articles())), 'errors': errors}
    (ROOT / 'data' / 'preparation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
