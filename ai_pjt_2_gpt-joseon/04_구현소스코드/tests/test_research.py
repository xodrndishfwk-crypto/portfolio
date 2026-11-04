import unittest
from unittest.mock import patch
from langchain_core.documents import Document
from history_rag.research import retain_selected_metadata, supported_retry_queries, collection_status, period_scope


class ResearchTests(unittest.TestCase):
    def test_king_in_event_condition_does_not_bypass_evidence_selection(self):
        from history_rag.explore import exact_period_condition
        from history_rag.timeline import load_periods
        periods = load_periods()
        self.assertEqual(exact_period_condition('태종이 낙마한 시기', periods), [])
        self.assertEqual(len(exact_period_condition('선조 25년 또는 1592년', periods)), 1)

    def test_year_document_cache_is_secondary_and_missing_page_is_not_fabricated(self):
        from history_rag.web_context import WebContext
        from history_rag.sources import SourceClient
        from history_rag.storage import Store
        from history_rag.settings import settings
        web = WebContext(SourceClient(Store(':memory:'), settings()))
        page = {'pageid': 42, 'title': '1592년', 'extract': '합성 연도 해설입니다.', 'revisions': [{'revid': 7}]}
        with patch.object(web, 'request', return_value={'query': {'pages': [page]}}) as request:
            doc = web.period_document({'year': 1592})
            web.period_document({'year': 1592})
            self.assertEqual(request.call_count, 1)
            self.assertFalse(doc['is_primary'])
            self.assertEqual(doc['title'], '1592년')
        with patch.object(web, 'request', return_value={'query': {'pages': [{'missing': True}]}}):
            self.assertIsNone(web.period_document({'year': 1593}))

    def test_king_only_does_not_limit_search_to_first_year(self):
        from history_rag.timeline import load_periods
        chosen, anchor, directory, book = period_scope(load_periods(), '태종이 낙마했어?', '태종')
        self.assertEqual(chosen, [])
        self.assertIsNone(anchor)
        self.assertEqual(directory, book)
        self.assertEqual(directory, 'ITKC_JT_C0')

    def test_different_king_overrides_selected_scope_without_dropping_metadata(self):
        from history_rag.timeline import load_periods
        periods = load_periods()
        selected = next(p for p in periods if p['king'] == '선조' and p['year'] == 1592)
        chosen, anchor, directory, book = period_scope(periods, '인조 때 일어난 사건', '인조', selected=selected)
        self.assertIsNone(anchor)
        self.assertEqual(chosen, [])
        self.assertEqual(directory, 'ITKC_JT_P0')
        self.assertEqual(len(retain_selected_metadata([], selected)), 1)

    def test_selected_period_survives_a_different_question_period(self):
        selected = {'id': 'A', 'title': '선택 연도', 'url': 'https://example.org/A'}
        evidence = [Document(page_content='질문의 다른 연도', metadata={'article_id': 'B', 'source_kind': '항목 메타데이터'})]
        result = retain_selected_metadata(evidence, selected)
        self.assertEqual({d.metadata['article_id'] for d in result}, {'A', 'B'})
        self.assertEqual(len(retain_selected_metadata(result, selected)), 2)

    def test_retry_rejects_invented_clue_and_bounds_requests(self):
        docs = [{'text': '합성 해설에는 말에서 떨어졌다는 기록이 있다.'}]
        plan = {'searches': [{'query': 'invented', 'quote': '없는 인용을 생성했다'},
                             {'query': '낙마', 'quote': '말에서 떨어졌다는 기록'},
                             {'query': '낙마', 'quote': '말에서 떨어졌다는 기록'},
                             {'query': '말', 'quote': '말에서 떨어졌다는 기록'}]}
        self.assertEqual(supported_retry_queries(plan, docs, 1), ['낙마'])

    def test_search_completion_does_not_assert_verification(self):
        self.assertIn('이야기를 정리', collection_status({'source_types': ['웹 해설']}))
        self.assertNotIn('확인 완료', collection_status({'has_primary_evidence': True}))


if __name__ == '__main__':
    unittest.main()
