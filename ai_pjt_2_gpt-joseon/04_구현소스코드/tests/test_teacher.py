import unittest
from history_rag.teacher import narrative_fields, needs_teacher_repair, apply_teacher_repair
from history_rag.encyclopedia import parse_article, parse_candidates


class TeacherTests(unittest.TestCase):
    def test_optional_null_fields_do_not_break_voice_check(self):
        fields = narrative_fields({'response': None, 'interpretation': None, 'claims': None, 'unknowns': None})
        self.assertFalse(needs_teacher_repair(fields))

    def test_hao_voice_and_system_prefaces_are_detected_but_quotes_are_preserved(self):
        self.assertTrue(needs_teacher_repair({'response': '그날 일어났소.'}))
        self.assertTrue(needs_teacher_repair({'response': '제공된 웹 해설에서는 이렇게 말한다.'}))
        self.assertFalse(needs_teacher_repair({'response': '“내가 했소.”라는 말이 적혀 있단다.'}))
        self.assertFalse(needs_teacher_repair({'response': '그날 일어났단다. 배경을 함께 살펴보자꾸나.'}))

    def test_style_repair_cannot_change_evidence_or_dates_in_translation(self):
        original = {'response': {'text': '그날 일어났소.', 'evidence': [{'number': 1, 'quote': '실제 구절'}]},
                    'claims': [{'claim': '원래 주장', 'verdict': '현재 근거 부족', 'explanation': '아직 모르겠소.'}],
                    'ai_translation': {'text': '원래 번역', 'evidence': []}, 'unknowns': []}
        repaired = apply_teacher_repair(original, {'response': '그날 일어났단다.', 'explanations': ['아직 모르겠구나.'],
                                                  'evidence': [{'number': 99, 'quote': '가짜'}], 'ai_translation': '바꾸면 안 됨'})
        self.assertEqual(repaired['response']['evidence'], original['response']['evidence'])
        self.assertEqual(repaired['claims'][0]['claim'], '원래 주장')
        self.assertEqual(repaired['ai_translation']['text'], '원래 번역')
        self.assertFalse(needs_teacher_repair(narrative_fields(repaired)))

    def test_encyclopedia_search_excludes_popular_links(self):
        html = '''<nav><a href="/Article/E000001">인기 항목</a></nav><div class="bo_gall"><a class="item" href="/Article/E0043666"><p class="subject">합성 사건</p><p class="desc">합성 설명</p></a></div>'''
        rows = parse_candidates(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'aks:E0043666')
        self.assertFalse(rows[0]['is_primary'])
        self.assertNotIn('CC BY-SA', rows[0]['license_name'])

    def test_encyclopedia_parser_excludes_metadata_and_media(self):
        html = '<article class="data_content"><section class="meta">툴팁</section><section><h3>내용</h3><p>실제 합성 본문</p><button>닫기</button><figure>미디어</figure></section></article>'
        text = parse_article(html)
        self.assertIn('실제 합성 본문', text)
        self.assertNotIn('툴팁', text)
        self.assertNotIn('미디어', text)
        self.assertNotIn('닫기', text)


if __name__ == '__main__':
    unittest.main()
