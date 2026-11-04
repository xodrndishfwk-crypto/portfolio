import unittest
from unittest.mock import Mock, patch
from langchain_core.documents import Document
from history_rag.pipeline import build_graph

class SupplementTests(unittest.TestCase):
    def test_missing_claim_triggers_web_fetch_and_renumbers_citations(self):
        old=Document(page_content='기존 자료는 해당 사실을 설명하지 않는다.',metadata={'article_id':'old','source_kind':'웹 해설','is_primary':False})
        article={'id':'aks:fixture','title':'시험용 사건','url':'https://example.org/fixture','source_kind':'웹 해설','is_primary':False,'text':'이 사건은 정조 때 일어났다.'}
        new=Document(page_content=article['text'],metadata={'article_id':article['id'],'source_kind':'웹 해설','is_primary':False})
        index=Mock();index.body.similarity_search.return_value=[new];index.splitter.split_text.side_effect=lambda s:[s]
        initial={'claims':[{'claim':'사건의 왕대','verdict':'현재 근거 부족','evidence':[]}], 'response':{'text':'확인하기 어렵구나.','evidence':[]}}
        final={'claims':[{'claim':'사건의 왕대','verdict':'기록상 뒷받침됨','evidence':[{'number':1,'quote':article['text']}]}], 'response':{'text':'정조 때의 일이란다.','evidence':[{'number':1,'quote':article['text']}]}}
        state={'question':'그 사건은 어느 왕 때야?','resolved_question':'그 사건은 어느 왕 때야?','claims':['사건의 왕대'],'evidence':[old],'history':[],'trace':{'bodies':[]}}
        with patch('history_rag.pipeline.ask_json',side_effect=[initial,{'queries':['사건 왕대']},final]) as llm, patch('history_rag.encyclopedia.Encyclopedia') as aks, patch('history_rag.web_context.WebContext') as wiki:
            aks.return_value.search.return_value=[{'id':'aks:fixture'}];aks.return_value.fetch.return_value=article
            wiki.return_value.search.return_value=[]
            graph=build_graph(None,None,index,None,{'history_turns':3,'top_k':7})
            result=graph.nodes['generate'].bound.invoke(state)
            self.assertEqual(aks.return_value.fetch.call_count,1)
            self.assertEqual(index.index_body.call_count,1)
            self.assertEqual(result['evidence'][0].page_content,article['text'])
            self.assertEqual(result['answer']['response']['text'],'정조 때의 일이란다.')
            self.assertEqual(result['trace']['supplement_queries'],['사건 왕대'])
            self.assertEqual(llm.call_count,3)
