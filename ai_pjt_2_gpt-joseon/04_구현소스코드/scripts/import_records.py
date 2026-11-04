"""이용 허락이 확인된 사용자 제공 기사만 로컬 JSON으로 가져온다."""
import argparse
import json
from pathlib import Path
from history_rag.storage import Store, digest, now


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    articles = json.loads(args.file.read_text(encoding='utf-8'))
    store = Store()
    for a in articles:
        if not all(a.get(k) for k in ['id', 'title', 'url', 'text', 'rights_basis']):
            raise ValueError('id/title/url/text/rights_basis가 필요합니다.')
        if a.get('rights_status') != 'permitted':
            raise ValueError('권리 허락이 확인된 자료만 가져올 수 있습니다.')
        a.update(body_hash=digest(a['text']), validation='valid', body_collected_at=now(), collection_method='user-provided permitted JSON')
        store.put(a)
    print(store.counts())


if __name__ == '__main__':
    main()
