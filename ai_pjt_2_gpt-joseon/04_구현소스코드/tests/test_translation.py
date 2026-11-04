import unittest
from unittest.mock import Mock, patch
from history_rag.storage import Store
from history_rag.translation import translate_source

class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(':memory:')
        self.store.put({'id':'fixture', 'title':'시험용 전사본', 'text':'王命史官記之。', 'source_kind':'한문 원문 전사본','rights_status':'permitted'})
    def tearDown(self):
        self.store.db.close()
    def test_translation_cached_and_bound_to_original(self):
        with patch('history_rag.translation.ask_json',return_value={'translation':'왕이 사관에게 이를 기록하라고 명하였다.'}) as call:
            one=translate_source(self.store,None,'fixture','王命史官記之。')
            two=translate_source(self.store,None,'fixture','王命史官記之。')
            self.assertFalse(one['cached']);self.assertTrue(two['cached'])
            self.assertEqual(call.call_count,1)
            self.assertEqual(one['translation'],two['translation'])
    def test_reject_uncollected_text_and_unknown_source(self):
        with self.assertRaises(ValueError): translate_source(self.store,None,'fixture','任意本文不許翻譯。')
        with self.assertRaises(ValueError): translate_source(self.store,None,'unknown','王命史官記之。')
    def test_reject_invalid_translation(self):
        with patch('history_rag.translation.ask_json',return_value={'translation':'王命史官記之。'}):
            with self.assertRaises(RuntimeError):translate_source(self.store,None,'fixture','王命史官記之。')
