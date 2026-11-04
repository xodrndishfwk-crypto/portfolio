import os
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from history_rag.storage import Store

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


class UITests(unittest.TestCase):
    def test_story_citations_compact_translation_and_suggestion_click(self):
        store = Store(':memory:')
        with patch.dict(os.environ, {'GMS_KEY': '', 'GMS_ENV_FILE': ''}), patch('history_rag.storage.Store', return_value=store):
            app = AppTest.from_file(APP, default_timeout=20).run()
            quote = '합성 기록에는 성 안이 텅 비었다고 적혀 있다.'
            cite = [{'number': 1, 'quote': quote}]
            answer = {'response': {'text': '임금은 그날 도착했소.', 'evidence': cite},
                      'aside': {'text': '그런데 성 안은 텅 비어 있었소.', 'evidence': cite},
                      'ai_translation': {'text': '성 안은 텅 비었다.', 'evidence': cite},
                      'claims': [], 'follow_up_questions': ['그 뒤에는 어디로 갔소?']}
            source = {'text': quote, 'metadata': {'title': '합성 자료', 'article_id': 'synthetic', 'source_kind': '합성 테스트', 'url': 'https://example.org/test'}}
            app.session_state['chats']['free_questions'] = [{'role': 'user', 'content': '합성 질문'}, {'role': 'assistant', 'answer': answer, 'sources': [source], 'research': {}}]
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any('잠깐, 이 대목을 보거라' in m.value for m in app.markdown))
            details = [e for e in app.expander if '기록 살펴보기' in e.label]
            self.assertEqual(len(details), 1)
            self.assertFalse(details[0].proto.expanded)
            self.assertFalse(any(e.label in ['주장별 확인 결과', '아직 확인되지 않은 부분', '사료 원문 · 기존 번역문'] for e in app.expander))
            self.assertFalse(any(s.label == '검색 방식' for s in app.selectbox))
            self.assertEqual(len(app.chat_message), 2)
            suggestion = next(b for b in app.button if b.label == '그 뒤에는 어디로 갔소?')
            suggestion.click().run()
            self.assertTrue(any('GMS' in w.value for w in app.warning))

    def test_free_chat_available_without_selection_or_articles(self):
        store = Store(':memory:')
        with patch.dict(os.environ, {'GMS_KEY': '', 'GMS_ENV_FILE': ''}), patch('history_rag.storage.Store', return_value=store):
            app = AppTest.from_file(APP, default_timeout=20).run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn('GPT-Joseon', app.title[0].value)
            self.assertEqual(len(app.chat_input), 1)
            self.assertIsNone(app.session_state['period'])
            self.assertTrue(any('GMS_KEY' in w.value for w in app.warning))

    def test_period_switch_keeps_global_and_period_chats_separate(self):
        store = Store(':memory:')
        with patch.dict(os.environ, {'GMS_KEY': '', 'GMS_ENV_FILE': ''}), patch('history_rag.storage.Store', return_value=store):
            app = AppTest.from_file(APP, default_timeout=20).run()
            app.session_state['chats']['free_questions'] = [{'role': 'user', 'content': '합성 자유 대화'}]
            app.selectbox(key='period').select_index(0).run()
            pid = app.session_state['period']
            self.assertEqual(len(app.chat_message), 0)
            app.session_state['chats'][pid] = [{'role': 'user', 'content': '합성 연도별 대화'}]
            app.selectbox(key='period').set_value(None).run()
            self.assertEqual(len(app.chat_message), 1)
            self.assertEqual(app.chat_message[0].markdown[0].value, '합성 자유 대화')
            self.assertEqual(len(app.exception), 0)


if __name__ == '__main__':
    unittest.main()
