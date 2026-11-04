"""합성 테스트 자료: 실제 확보 기사 건수에 포함하지 않는다."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from langchain_core.documents import Document
from history_rag.sources import parse_search, parse_body, SourceClient
from history_rag.storage import Store, digest
from history_rag.settings import settings
from history_rag.pipeline import validate_answer, build_graph, validate_enrichment, prioritize_collected_primary
from history_rag.index import metadata_text


class CoreTests(unittest.TestCase):
    def test_xml_original_id_and_dates(self):
        xml = '<response><result><doc><field name="자료ID">original_ID</field><field name="기사명">합성 기사</field><field name="편년월">윤02</field><field name="간행년">1974</field><field name="검색필드">발췌 &lt;em&gt;소문&lt;/em&gt;</field></doc></result></response>'
        a = parse_search(xml)[0]
        self.assertEqual(a['id'], 'original_ID')
        self.assertEqual(a['month_original'], '윤02')
        self.assertEqual(a['year'], '')
        self.assertEqual(a['publication_year'], '1974')
        self.assertEqual(a['snippet'], '발췌 소문')

    def test_empty_and_error_body(self):
        for html in ['<nav>메뉴</nav>', '<html>페이지를 찾을 수 없습니다</html>', '<div class="text_body"></div>']:
            self.assertEqual(parse_body(html), '')
        self.assertEqual(parse_body('<div class="text_body">합성 기사 본문</div><nav>메뉴</nav>'), '합성 기사 본문')

    def test_metadata_not_fulltext(self):
        a = {'id': 'x', 'title': '합성', 'snippet': '발췌'}
        self.assertIn('발췌', metadata_text(a))
        self.assertNotIn('text:', metadata_text(a))

    def test_store_dedup_relations(self):
        s = Store(':memory:')
        for _ in range(2):
            s.put({'id': 'x'})
        self.assertEqual(len(s.articles()), 1)
        s.link('one', 'doc', '독립 관계')
        s.link('two', 'doc', '독립 관계')
        self.assertEqual(s.related('one'), ['doc'])
        self.assertEqual(s.related('two'), ['doc'])

    def test_cache_failure_and_empty(self):
        s = Store(':memory:')
        s.cache_put('x', 'failed', [])
        self.assertEqual(s.cache_get('x', 3600)['status'], 'failed')
        s.cache_put('x', 'empty', [])
        self.assertEqual(s.cache_get('x', 3600)['status'], 'empty')
        self.assertIsNone(s.cache_get('x', -1, -1))

    def test_citation_numbers_and_exact_quote(self):
        evidence = [Document(page_content='이것은 합성 검증을 위한 본문입니다.', metadata={'source_kind': '기존 번역'})]
        for n, quote in [(9, '이것은 합성 검증'), (1, '존재하지 않는 문장입니다')]:
            result = validate_answer({'claims': [{'claim': 'x', 'verdict': '기록상 뒷받침됨', 'evidence': [{'number': n, 'quote': quote}]}]}, evidence)
            self.assertEqual(result['claims'][0]['verdict'], '현재 근거 부족')
        result = validate_answer({'claims': [{'claim': 'x', 'verdict': '기록상 뒷받침됨', 'evidence': [{'number': 1, 'quote': '합성 검증을 위한 본문입니다.'}]}]}, evidence)
        self.assertEqual(result['claims'][0]['verdict'], '기록상 뒷받침됨')

    def test_metadata_cannot_establish_body_claim(self):
        evidence = [Document(page_content='합성 메타데이터 설명입니다.', metadata={'source_kind': '항목 메타데이터'})]
        result = validate_answer({'claims': [{'claim': 'x', 'verdict': '기록상 뒷받침됨', 'evidence': [{'number': 1, 'quote': '합성 메타데이터 설명입니다.'}]}]}, evidence)
        self.assertEqual(result['claims'][0]['verdict'], '현재 근거 부족')

    def test_no_body_storage_before_rights_check(self):
        s = Store(':memory:')
        config = {**settings(), 'allow_body_storage': False}
        with self.assertRaises(RuntimeError):
            SourceClient(s, config).fetch({'id': 'test'})

    def test_graph_nodes(self):
        graph = build_graph(None, None, None, None, settings())
        self.assertEqual(set(graph.get_graph().nodes), {'__start__', 'retrieve', 'generate', '__end__'})

    def test_universal_claim_not_proven_by_one_case(self):
        docs = [Document(page_content='합성 사례는 하나만 존재합니다.', metadata={'source_kind': '합성 테스트'})]
        a = validate_answer({'claims': [{'claim': '모든 왕은 항상 같았다', 'verdict': '기록상 뒷받침됨', 'evidence': [{'number': 1, 'quote': '합성 사례는 하나만 존재합니다.'}]}]}, docs)
        self.assertEqual(a['claims'][0]['verdict'], '현재 근거 부족')

    def test_fun_aside_still_requires_real_quote(self):
        docs = [Document(page_content='합성 기록: 성 안은 텅 비어 있었다.', metadata={'source_kind': '합성 테스트'})]
        result = validate_enrichment({'text': '왕이 몰래 잔치를 열었소.', 'evidence': [{'number': 1, 'quote': '왕은 몰래 잔치를 열었다.'}]}, docs)
        self.assertEqual(result['text'], '')

    def test_aside_can_add_supported_new_detail(self):
        docs = [Document(page_content='합성 기록: 성 안은 텅 비어 있었다.', metadata={'source_kind': '합성 테스트'})]
        result = validate_enrichment({'text': '흥미롭게도 성 안은 텅 비어 있었소.', 'evidence': [{'number': 1, 'quote': '성 안은 텅 비어 있었다.'}]}, docs, {'text': '임금은 이날 도착하였소.'})
        self.assertTrue(result['text'])

    def test_exact_repetition_removed_from_aside(self):
        docs = [Document(page_content='합성 기록: 성 안은 텅 비어 있었다.', metadata={'source_kind': '합성 테스트'})]
        text = '성 안은 텅 비어 있었소.'
        result = validate_enrichment({'text': text, 'evidence': [{'number': 1, 'quote': '성 안은 텅 비어 있었다.'}]}, docs, {'text': text})
        self.assertEqual(result['text'], '')

    def test_new_primary_not_crowded_out_by_secondary_results(self):
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from types import SimpleNamespace
        index = SimpleNamespace(splitter=RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=0))
        metadata = Document(page_content='합성 연도', metadata={'source_kind': '항목 메타데이터'})
        web = Document(page_content='합성 웹 해설', metadata={'article_id': 'web', 'source_kind': '웹 해설'})
        primary = {'id': 'original', 'title': '합성 사료', 'url': 'https://example.org/test', 'text': '합성 사료: 임금이 도착했고 성 안은 텅 비어 있었다.', 'source_kind': '한문 원문 전사본'}
        result = prioritize_collected_primary([metadata, web], [primary], index, 1)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].metadata['source_kind'], '항목 메타데이터')
        self.assertEqual(result[1].metadata['article_id'], 'original')

    def test_late_conclusion_found_by_claim_is_not_lost_to_document_prefix(self):
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from types import SimpleNamespace
        index = SimpleNamespace(splitter=RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=0))
        late = Document(page_content='합성 사건의 결말: 부하들에게 살해되었다.', metadata={'article_id': 'ending', 'source_kind': '웹 해설'})
        primary = {'id': 'early', 'title': '도주 기록', 'url': 'https://example.org/early', 'text': '도망쳤다는 기록만 있다.', 'source_kind': '한문 원문 전사본'}
        result = prioritize_collected_primary([], [primary], index, 1, claim_hits=[late])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].metadata['article_id'], 'ending')

    def test_search_cache_reuses_response_and_refreshes(self):
        store = Store(':memory:')
        source = SourceClient(store, settings())
        xml = '<response><doc><field name="자료ID">SYNTHETIC</field><field name="기사명">합성 기사</field></doc></response>'
        with patch.object(source, 'get', return_value=xml) as get:
            source.search('합성')
            source.search('합성')
            self.assertEqual(get.call_count, 1)
            source.search('합성', refresh=True)
            self.assertEqual(get.call_count, 2)


if __name__ == '__main__':
    unittest.main()
