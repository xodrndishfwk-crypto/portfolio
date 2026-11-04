import unittest
from history_rag.timeline import parse_periods, load_periods, match_periods


class TimelineTests(unittest.TestCase):
    def test_real_catalogue_counts_and_extents(self):
        rows = load_periods()
        self.assertEqual(len(rows), 542)
        self.assertEqual(len({p['king'] for p in rows}), 27)
        self.assertEqual({p['year'] for p in rows}, set(range(1392, 1911)))
        self.assertEqual(len({p['id'] for p in rows}), len(rows))

    def test_actual_reign_year_mapping(self):
        rows = load_periods()
        self.assertEqual(match_periods(rows, '선조 25년')[0]['year'], 1592)
        self.assertEqual(match_periods(rows, '태조 1년')[0]['year'], 1392)
        self.assertEqual(match_periods(rows, '태종 1년')[0]['year'], 1401)
        self.assertEqual(match_periods(rows, '순종 즉위년')[0]['year'], 1907)
        self.assertEqual(match_periods(rows, '순종 3년')[0]['year'], 1910)

    def test_same_ce_year_multiple_reigns(self):
        rows = match_periods(load_periods(), '1907년')
        self.assertEqual({p['king'] for p in rows}, {'고종', '순종'})

    def test_explicit_question_overrides_selected_hints(self):
        rows = match_periods(load_periods(), '태종 4년 낙마', king='선조', year=None)
        self.assertEqual(rows[0]['title'], '태종 4년')

    def test_catalogue_excludes_general_history_and_preserves_leap_month(self):
        html = '''<table><tr><td><a href="#/dir/node?dataId=TEST_A00">합성왕 즉위년</a></td><td>연호</td><td>1592</td><td><a onclick="go('/dir/node?dataId=TEST_A00_06B')">윤 6월</a></td></tr><tr><td>총서</td><td></td><td></td><td></td></tr></table>'''
        rows = parse_periods(html, '합성 목차', 'TEST')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['months'][0]['label'], '윤 6월')
