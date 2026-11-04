import unittest
from history_rag.transcriptions import chinese_number, find_day_section


class TranscriptionTests(unittest.TestCase):
    def test_chinese_year_labels(self):
        self.assertEqual(chinese_number(1), '一')
        self.assertEqual(chinese_number(10), '十')
        self.assertEqual(chinese_number(25), '二十五')
        self.assertEqual(chinese_number(40), '四十')

    def test_leap_month_not_confused(self):
        sections = [{'level': '2', 'line': '六月'}, {'level': '3', 'line': '6月22日', 'index': '3'},
                    {'level': '2', 'line': '閏六月'}, {'level': '3', 'line': '6月22日', 'index': '8'}]
        self.assertEqual(find_day_section(sections, 6, 22)['index'], '3')
        self.assertEqual(find_day_section(sections, 6, 22, True)['index'], '8')
        self.assertIsNone(find_day_section(sections, 6, 23))
