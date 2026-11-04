"""ITKC 공식 검색 XML과 별도 웹 본문 열람 경로를 구분한다."""
import re
import os
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup
from .storage import now, digest


def clean(text):
    return re.sub(r'\s+', ' ', BeautifulSoup(text or '', 'html.parser').get_text(' ', strip=True)).strip()


def parse_search(xml):
    root = ET.fromstring(xml)
    rows = []
    for doc in root.findall('.//doc'):
        fields = {f.attrib.get('name'): ''.join(f.itertext()) for f in doc.findall('field')}
        article_id = fields.get('자료ID', '')
        title = clean(fields.get('기사명', ''))
        if not article_id or not title:
            continue
        year, month, day = (fields.get(k, '') for k in ('편년서기년', '편년월', '편년일'))
        rows.append({'id': article_id, 'title': title, 'service': '한국고전종합DB',
                     'institution': '한국고전번역원', 'source_kind': '기존 번역',
                     'collection': fields.get('서명', ''), 'king': fields.get('서명', '').split('실록')[0],
                     'date_original': ' '.join(x for x in [year, month, day] if x),
                     'year': year, 'month_original': month, 'day_original': day,
                     'date_precision': 'day' if day else ('month' if month else ('year' if year else 'unknown')),
                     'date_converted': False, 'snippet': clean(fields.get('검색필드', '')),
                     'dci': fields.get('DCI_s', ''), 'category': fields.get('주제분류', ''),
                     'translator': fields.get('역자', ''), 'publisher': fields.get('간행처', ''),
                     'publication_year': fields.get('간행년', ''), 'raw_metadata': fields,
                     'url': 'https://db.itkc.or.kr/dir/node?' + urlencode({'dataId': article_id}),
                     'collected_at': now(), 'collection_method': 'ITKC search XML',
                     'rights_status': 'unverified', 'validation': 'metadata_only'})
    return rows


def parse_body(html, service='itkc'):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('script,style,nav,header,footer,.footnote,.주석'):
        node.decompose()
    selectors = ['.ins_view_pd', '.ins_view', '#contentBody', '.text_body', '.textBody', '.original'] if service == 'itkc' else ['.ins_view_pd', '.ins_view', '.view_cont .paragraph', '.paragraph']
    for selector in selectors:
        nodes = soup.select(selector)
        if nodes:
            paragraphs = [n.get_text(' ', strip=True) for n in nodes]
            text = '\n'.join(paragraphs)
            text = re.sub(r'[ \t]+', ' ', text).strip()
            if text and not any(x in text[:100] for x in ['접근이 제한', '페이지를 찾을 수', '로그인이 필요']):
                return text
    return ''


class SourceClient:
    def __init__(self, store, config):
        self.store, self.config = store, config
        self.session = requests.Session()
        contact = os.getenv('HISTORY_SOURCE_CONTACT', '').strip()
        self.session.headers['User-Agent'] = 'TaejeongHistoryResearch/0.2 (educational local RAG' + (f'; {contact}' if contact else '') + ')'
        self.last_request = 0

    def get(self, url, params=None):
        for attempt in range(self.config['retries'] + 1):
            time.sleep(max(0, self.config['request_interval'] - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.session.get(url, params=params, timeout=self.config['timeout'])
                if response.status_code in (429, 500, 502, 503, 504) and attempt < self.config['retries']:
                    delay = response.headers.get('Retry-After', '')
                    if delay and (not delay.isdigit() or int(delay) > 60):
                        raise RuntimeError('출처의 대기 시간이 길어 수집을 보류합니다.')
                    time.sleep(int(delay) if delay.isdigit() else 2 ** attempt)
                    continue
                response.raise_for_status()
                response.encoding = 'utf-8'
                return response.text
            except requests.RequestException:
                if attempt == self.config['retries']:
                    raise RuntimeError('외부 자료 요청에 실패했습니다. 잠시 후 재시도하세요.') from None
        raise RuntimeError('외부 자료 요청 보류')

    def search(self, query, section='JT_BD', start=0, rows=None, refresh=False, directory=None):
        rows = rows or self.config['candidate_count']
        key = f'search:{section}:{query}:{start}:{rows}:{directory or ""}'
        cached = None if refresh else self.store.cache_get(key, self.config['cache_hours'] * 3600, self.config['failure_cache_minutes'] * 60)
        if cached:
            return cached['data'] if cached['status'] in ('ok', 'empty') else []
        try:
            params = {'secId': section, 'start': start, 'rows': rows}
            if directory:
                params['q'] = f'query†{query}$opDir†{directory}'
            else:
                params['keyword'] = query
            xml = self.get('https://db.itkc.or.kr/openapi/search', params)
            articles = parse_search(xml)
            for a in articles:
                if not self.store.get(a['id']):
                    self.store.put(a)
            self.store.cache_put(key, 'ok' if articles else 'empty', articles)
            return articles
        except Exception:
            self.store.cache_put(key, 'failed', [])
            raise

    def fetch(self, article, refresh=False):
        existing = self.store.get(article['id'])
        if existing and existing.get('text') and not refresh:
            return existing
        if not self.config['allow_body_storage']:
            raise RuntimeError('본문 저장 이용 조건이 미확인입니다. 출처 대장을 확인하세요.')
        if article.get('rights_status') != 'permitted' or not article.get('rights_basis'):
            raise RuntimeError('이 기사의 본문 저장 이용 근거가 확인되지 않았습니다.')
        key = 'body:' + article['id']
        cached = None if refresh else self.store.cache_get(key, self.config['cache_hours'] * 3600)
        if cached and cached['status'] != 'ok':
            return existing or article
        try:
            html = self.get(article['url'])
            soup = BeautifulSoup(html, 'html.parser')
            container = soup.select_one('[data-viewnode-id]')
            if container is None or container.get('data-viewnode-id') != article['id']:
                text = ''
            else:
                text = parse_body(html)
        except RuntimeError:
            self.store.cache_put(key, 'failed', {'id': article['id']})
            raise
        result = {**article, 'text': text, 'text_translation': text, 'text_original': '', 'body_hash': digest(text) if text else '',
                  'body_collected_at': now(), 'collection_method': 'ITKC web node (not fulltext API)',
                  'validation': 'valid' if text else 'body_failed'}
        self.store.put(result)
        self.store.cache_put(key, 'ok' if text else 'failed', {'id': article['id']})
        return result
