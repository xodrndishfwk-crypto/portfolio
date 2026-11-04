"""한국민족문화대백과사전의 공개 검색과 이용 가능한 항목 본문. 미디어는 수집하지 않는다."""
import re
from bs4 import BeautifulSoup
from .storage import now, digest

BASE = 'https://encykorea.aks.ac.kr'
GUIDE = BASE + '/Guide/ContentUse'


def parse_candidates(html):
    soup = BeautifulSoup(html, 'html.parser')
    result, seen = [], set()
    # 인기 검색어/추천 항목은 제외하고 실제 검색 결과만 읽는다.
    for a in soup.select('.bo_gall a.item[href]'):
        path = a.get('href', '')
        if not re.fullmatch(r'/Article/E\d+', path) or path in seen:
            continue
        title = a.select_one('.subject')
        if not title:
            continue
        seen.add(path)
        snippet = a.select_one('.desc')
        result.append({'id': 'aks:' + path.rsplit('/', 1)[-1], 'title': title.get_text(' ', strip=True),
            'url': BASE + path, 'snippet': snippet.get_text(' ', strip=True)[:1000] if snippet else '',
            'collection': '한국민족문화대백과사전', 'service': '한국학중앙연구원 · 한국민족문화대백과사전',
            'source_kind': '웹 해설', 'is_primary': False, 'date_original': '사건 날짜는 본문에서 확인',
            'rights_status': 'permitted', 'rights_basis': GUIDE + ' · 이용 가능한 콘텐츠 범위: 항목 원고(본문) 전체, 출처 표시',
            'license': GUIDE, 'license_name': '공공저작물 이용 안내', 'attribution': '한국민족문화대백과사전',
            'validation': 'metadata_only'})
    return result


def parse_article(html):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('article.data_content')
    if not root:
        return ''
    for node in root.select('script,style,button,img,figure,.tooltip_layer,.meta'):
        node.decompose()
    return '\n'.join(line.strip() for line in root.get_text('\n', strip=True).splitlines() if line.strip())


class Encyclopedia:
    def __init__(self, source):
        self.source, self.store = source, source.store

    def search(self, query, refresh=False):
        query = str(query).strip()[:100]
        if not query:
            return []
        key = 'aks_search:' + query
        cached = None if refresh else self.store.cache_get(key, 86400)
        if cached:
            return cached['data']
        rows = parse_candidates(self.source.get(BASE + '/Article/Search', {'query': query}))[:3]
        self.store.cache_put(key, 'ok' if rows else 'empty', rows)
        return rows

    def fetch(self, article, refresh=False):
        if not re.fullmatch(r'https://encykorea\.aks\.ac\.kr/Article/E\d+', article.get('url', '')):
            raise RuntimeError('허용된 백과사전 항목 URL이 아닙니다.')
        cached = self.store.get(article['id'])
        if cached and cached.get('text') and not refresh:
            return cached
        if not self.source.config.get('allow_body_storage'):
            raise RuntimeError('본문 저장 설정을 확인하세요.')
        text = parse_article(self.source.get(article['url']))
        if not text:
            return {**article, 'validation': 'body_failed'}
        doc = {**article, 'text': text, 'body_hash': digest(text), 'collected_at': now(),
               'attribution': f"{article['title']}, 『한국민족문화대백과사전』", 'validation': 'valid',
               'collection_method': 'AKS public search + article text; media excluded'}
        self.store.put(doc)
        return doc
