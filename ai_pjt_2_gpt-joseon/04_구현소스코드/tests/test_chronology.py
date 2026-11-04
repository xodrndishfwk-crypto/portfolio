import unittest
from history_rag.chronology import chronology_periods, chronology_evidence, chronology_answer
from history_rag.timeline import load_periods



class ChronologyTests(unittest.TestCase):
    def test_known_year_and_citation(self):
        periods = chronology_periods('1793년은 어느 왕대야?', [], load_periods())
        assert len(periods) == 1 and periods[0]['king'] == '정조'
        docs = chronology_evidence(periods)
        answer = chronology_answer(periods, docs)
        assert '정조 17년' in answer['response']['text']
        assert answer['response']['evidence'][0]['quote'] in docs[0].page_content


    def test_followup_year(self):
        history = [{'role': 'assistant', 'content': '그 월식은 1793년이란다.'}]
        assert chronology_periods('어느 왕대야?', history, load_periods())[0]['king'] == '정조'
        assert not chronology_periods('태조는 어느 왕대야?', history, load_periods())


    def test_event_questions_use_research(self):
        assert not chronology_periods('1793년 어느 왕이 전쟁을 했어?', [], load_periods())
        assert not chronology_periods('1793년 어느 왕이야? 배경도 알려줘', [], load_periods())


    def test_transition_year_requires_date(self):
        periods = chronology_periods('1907년은 어느 왕대야?', [], load_periods())
        assert len(periods) == 2
        assert '날짜' in chronology_answer(periods, chronology_evidence(periods))['response']['text']

    def test_natural_followup_keeps_verified_king(self):
        history = [{'role':'assistant','content':'1793년은 정조 17년이란다. 정조가 다스리던 시기야.'}]
        for question in ['누가 다스리던 시기라구?', '누가 다스렸어?', '그때 임금이 누구야?', '어느 임금이 다스렸지?']:
            with self.subTest(question=question):
                rows=chronology_periods(question,history,load_periods())
                self.assertEqual(rows[0]['king'],'정조')
                self.assertIn('정조가',chronology_answer(rows,chronology_evidence(rows))['response']['text'])
        self.assertFalse(chronology_periods('누가 다스렸고 왜 전쟁이 났어?',history,load_periods()))

    def test_graph_revalidates_followup_without_unrelated_web_evidence(self):
        from history_rag.pipeline import build_graph
        from unittest.mock import patch
        history=[{'role':'assistant','content':'그 월식은 1793년이라는 추정이 있단다.'}]
        graph=build_graph(None,None,None,None,{})
        with patch('history_rag.pipeline.ask_json') as model:
            first=graph.invoke({'question':'어느 왕 때야?','history':history})
            history.append({'role':'assistant','content':first['answer']['response']['text']})
            second=graph.invoke({'question':'누가 다스리던 시기라구?','history':history})
            self.assertIn('정조가',second['answer']['response']['text'])
            self.assertEqual(second['evidence'][0].metadata['source_kind'],'왕력 대조')
            model.assert_not_called()
