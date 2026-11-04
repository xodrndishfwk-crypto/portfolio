"""허용된 실록 한문 전사본. 공식 번역문·국편 대조본으로 표시하지 않는다."""
import json
import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from .storage import digest, now

API = 'https://zh.wikisource.org/w/api.php'


def chinese_number(number):
    digits = '零一二三四五六七八九'
    if number < 10:
        return digits[number]
    tens, ones = divmod(number, 10)
    return (digits[tens] if tens > 1 else '') + '十' + (digits[ones] if ones else '')


def find_day_section(sections, month, day, leap=False):
    month_heading = ''
    for section in sections:
        if section.get('level') == '2':
            month_heading = section.get('line', '')
        line = BeautifulSoup(section.get('line', ''), 'html.parser').get_text(strip=True)
        if line == f'{month}月{day}日' and bool('閏' in month_heading or '闰' in month_heading) == leap:
            return section
    return None


class TranscriptionClient:
    def __init__(self, source):
        self.source, self.store = source, source.store

    def request(self, params):
        old = self.source.config['request_interval']
        self.source.config['request_interval'] = max(old, 6.1)
        try:
            data = json.loads(self.source.get(API, {**params, 'format': 'json', 'formatversion': 2}))
            return data
        finally:
            self.source.config['request_interval'] = old

    def fetch_for(self, article, period):
        if not period or not article.get('day_original') or not article.get('month_original'):
            return None
        if str(period['year']) != str(article.get('year')):
            return None
        chinese_title = re.search(r'[（(]([^）)]+)[）)]', period.get('collection', ''))
        reign = re.search(r'^(\d+)년$', period.get('reign_label', ''))
        if not chinese_title or not reign:
            return None
        month = re.search(r'\d+', article['month_original'])
        day = re.search(r'\d+', article['day_original'])
        if not month or not day:
            return None
        month, day = int(month.group()), int(day.group())
        month_nodes = [m for m in period.get('months', []) if article['id'].startswith(m['id'] + '_')]
        if len(month_nodes) != 1:
            return None
        leap = '윤' in month_nodes[0]['label']
        title = '朝鮮王朝實錄/' + chinese_title.group(1) + '/' + chinese_number(int(reign.group(1))) + '年'
        cache_key = f'wikisource:day:{title}:{month}:{day}:{leap}'
        cache = self.store.cache_get(cache_key, 7 * 86400)
        if cache and cache['status'] == 'ok':
            return self.store.get(cache['data']['id'])
        rights = self.store.cache_get('wikisource:license', 30 * 86400)
        if not rights:
            info = self.request({'action': 'query', 'meta': 'siteinfo', 'siprop': 'rightsinfo'})
            license_url = info.get('query', {}).get('rightsinfo', {}).get('url', '')
            if 'creativecommons.org/licenses/by-sa/4.0' not in license_url:
                return None
            self.store.cache_put('wikisource:license', 'ok', license_url)
        sections = self.store.cache_get('wikisource:sections:' + title, 7 * 86400)
        if sections:
            listing = sections['data']
        else:
            listing = self.request({'action': 'parse', 'page': title, 'prop': 'sections'}).get('parse', {}).get('sections', [])
            self.store.cache_put('wikisource:sections:' + title, 'ok' if listing else 'empty', listing)
        section = find_day_section(listing, month, day, leap)
        if not section:
            return None
        parsed = self.request({'action': 'parse', 'page': title, 'section': section['index'], 'prop': 'text|revid'}).get('parse', {})
        html = parsed.get('text', '')
        soup = BeautifulSoup(html, 'html.parser')
        for n in soup.select('.mw-editsection, .reference, script, style, .noprint'):
            n.decompose()
        original = soup.get_text('\n', strip=True)
        if not original or not parsed.get('pageid') or not parsed.get('revid'):
            return None
        doc_id = f"wikisource:zh:{parsed['pageid']}:{section['index']}"
        label = f"{period['title']} {'윤 ' if leap else ''}{month}월 {day}일"
        text = f"날짜: {label} ({period['year']}년, 사료의 날짜 표기·양력 환산 안 함)\n한문 원문 전사본:\n{original}"
        url = 'https://zh.wikisource.org/wiki/' + quote(title) + '#' + quote(section.get('anchor', section['line']))
        doc = {'id': doc_id, 'title': label + ' · 실록 한문 전사본', 'url': url,
               'collection': period['collection'], 'service': '위키문헌 (Wikisource)',
               'source_kind': '한문 원문 전사본', 'is_primary': True, 'text': text,
               'text_original': original, 'text_translation': '', 'date_original': label,
               'year': str(period['year']), 'date_precision': 'day', 'date_converted': False,
               'body_hash': digest(text), 'validation': 'valid', 'rights_status': 'permitted',
               'rights_basis': 'Wikisource 사이트 API에서 확인한 텍스트 CC BY-SA 4.0, 기여자·판본·변경 표시',
               'license': 'https://creativecommons.org/licenses/by-sa/4.0/',
               'revision_url': f"https://zh.wikisource.org/w/index.php?oldid={parsed['revid']}",
               'related_official_candidate': article['id'], 'relation_basis': '왕력·서기년·월·일·윤달 대조. 개별 기사 동일성 및 국편 판본 대조 미완료',
               'collected_at': now(), 'collection_method': 'Wikisource MediaWiki parse API, single dated section'}
        self.store.put(doc)
        self.store.cache_put(cache_key, 'ok', {'id': doc_id})
        return doc
