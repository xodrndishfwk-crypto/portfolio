"""일반 웹 해설 검색 어댑터. 한국어 위키백과의 해설을 1차 사료와 구분한다."""
import json
import re
from urllib.parse import quote
from .sources import clean
from .storage import digest, now

API = 'https://ko.wikipedia.org/w/api.php'
LICENSE = 'https://creativecommons.org/licenses/by-sa/4.0/'


class WebContext:
    def __init__(self, source):
        self.source = source
        self.store = source.store

    def request(self, params):
        old = self.source.config['request_interval']
        self.source.config['request_interval'] = max(old, self.source.config.get('web_request_interval', 6.1))
        try:
            result = json.loads(self.source.get(API, {**params, 'format': 'json', 'formatversion': 2}))
            if 'error' in result:
                raise RuntimeError('웹 검색 API 오류')
            return result
        finally:
            self.source.config['request_interval'] = old

    def search(self, query, refresh=False):
        # 질문 전체를 AND 조건처럼 보내면 관계없는 장문만 남을 수 있어 핵심어로 제한한다.
        query = ' '.join(re.findall(r'[가-힣A-Za-z0-9]+', query)[:3])
        key = 'wiki_search:' + query
        cache = None if refresh else self.store.cache_get(key, 86400)
        if cache:
            return cache['data']
        data = self.request({'action': 'query', 'list': 'search', 'srsearch': query,
                             'srlimit': self.source.config.get('web_result_count', 3)})
        rows = []
        for row in data.get('query', {}).get('search', []):
            rows.append({'id': f"wiki:ko:{row['pageid']}", 'page_id': row['pageid'], 'title': row['title'],
                         'url': 'https://ko.wikipedia.org/wiki/' + quote(row['title'].replace(' ', '_')),
                         'collection': '한국어 위키백과', 'service': '한국어 위키백과',
                         'source_kind': '웹 해설', 'is_primary': False, 'snippet': clean(row['snippet']),
                         'date_original': '해설 문서: 사건 날짜는 본문에서 확인', 'rights_status': 'permitted',
                         'rights_basis': 'Wikimedia Terms of Use, 텍스트 CC BY-SA 4.0, 문서/기여 이력 링크와 변경 표시',
                         'license': LICENSE, 'attribution': '한국어 위키백과 기여자',
                         'validation': 'metadata_only'})
        self.store.cache_put(key, 'ok' if rows else 'empty', rows)
        return rows

    def fetch(self, article, refresh=False):
        existing = self.store.get(article['id'])
        if existing and existing.get('text') and not refresh:
            return existing
        data = self.request({'action': 'query', 'prop': 'extracts|revisions', 'pageids': article['page_id'],
                             'explaintext': 1, 'rvprop': 'ids|timestamp'})
        pages = data.get('query', {}).get('pages', [])
        page = pages[0] if pages else {}
        text = page.get('extract', '').strip()
        if not text or page.get('missing'):
            return {**article, 'validation': 'body_failed'}
        revision = page.get('revisions', [{}])[0]
        result = {**article, 'text': text, 'body_hash': digest(text), 'validation': 'valid',
                  'revision_url': f"https://ko.wikipedia.org/w/index.php?oldid={revision.get('revid', '')}",
                  'history_url': article['url'] + '?action=history', 'revision_timestamp': revision.get('timestamp', ''),
                  'collected_at': now(), 'collection_method': 'MediaWiki extracts API (secondary source)'}
        self.store.put(result)
        return result

    def period_document(self, period, refresh=False):
        """왕력 연도에 대응하는 서기년 문서를 별도 수집한다. 실록/조선 전용 해설로 가장하지 않는다."""
        title = f"{period['year']}년"
        key = 'year_document:' + title
        cached = None if refresh else self.store.cache_get(key, 86400)
        if cached:
            return cached['data'] or None
        data = self.request({'action': 'query', 'titles': title, 'prop': 'extracts|revisions',
                             'explaintext': 1, 'rvprop': 'ids|timestamp'})
        page = next(iter(data.get('query', {}).get('pages', [])), {})
        if page.get('missing') or not page.get('extract', '').strip() or page.get('title') != title:
            self.store.cache_put(key, 'empty', {})
            return None
        revision = page.get('revisions', [{}])[0]
        text = page['extract'].strip()
        doc = {'id': f"wiki:ko:{page['pageid']}", 'page_id': page['pageid'], 'title': title,
               'url': 'https://ko.wikipedia.org/wiki/' + quote(title), 'text': text,
               'collection': '한국어 위키백과 연도별 해설', 'service': '한국어 위키백과',
               'source_kind': '웹 해설', 'is_primary': False, 'date_original': f"서기 {period['year']}년 해설",
               'rights_status': 'permitted', 'rights_basis': 'Wikimedia 텍스트 CC BY-SA 4.0, 판본/기여자 및 변경 표시',
               'license': LICENSE, 'body_hash': digest(text), 'validation': 'valid',
               'revision_url': f"https://ko.wikipedia.org/w/index.php?oldid={revision.get('revid', '')}",
               'collection_method': 'MediaWiki extracts API, selected year document', 'collected_at': now()}
        self.store.put(doc)
        self.store.cache_put(key, 'ok', doc)
        return doc
