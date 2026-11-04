"""실제 GMS·Chroma·LangGraph 통합 검증. 자료는 전부 합성이며 실제 기사 수에서 제외."""
import json
import tempfile
import time
from pathlib import Path
from history_rag.settings import settings, ROOT
from history_rag.storage import Store, digest
from history_rag.llm import model, embeddings
from history_rag.index import Index
from history_rag.pipeline import build_graph


def main():
    config = {**settings(), 'allow_llm_transfer': True, 'allow_body_storage': True, 'enable_web_context': False}
    synthetic = {'id': 'SYNTHETIC_TEST_ONLY', 'title': '합성 검증 자료: 요청과 처분', 'url': 'https://example.org/synthetic-test',
                 'collection': '합성 테스트 자료', 'date_original': '날짜 미상', 'snippet': '형벌 요청과 최종 처분이 다른 합성 사례',
                 'text': '이 문서는 역사 기록이 아닌 합성 테스트 자료다. 가상의 관청은 가상 인물 다온에게 장형 백 대를 요청하였다. 가상의 왕은 그 요청을 받아들이지 않고 장형 이십 대로 감하였다. 그 인물의 혐의가 객관적으로 사실인지는 기록하지 않았다.',
                 'rights_status': 'permitted', 'rights_basis': '프로젝트 자체 작성 합성 테스트', 'validation': 'valid', 'source_kind': '합성 테스트'}
    synthetic['body_hash'] = digest(synthetic['text'])
    started = time.monotonic()
    report = {'synthetic_only': True, 'model': config['model'], 'embedding_model': config['embedding_model']}
    with tempfile.TemporaryDirectory() as temp:
        index = Index(embeddings(config), config, Path(temp) / 'chroma')
        index.index_metadata([synthetic])
        index.index_body(synthetic['id'], synthetic)
        first = index.counts()
        index.index_metadata([synthetic])
        index.index_body(synthetic['id'], synthetic)
        report['index_counts'] = first
        report['idempotent'] = first == index.counts()
        index.config['search_mode'] = 'mmr'
        docs = index.retrieve(synthetic, '처음 요청한 형벌과 실제 처분은 같았어?')
        report['mmr_evidence_count'] = len(docs)
        report['selected_metadata_present'] = docs[0].metadata['source_kind'] == '항목 메타데이터'
        report['own_body_present'] = any(d.metadata['source_kind'] == '합성 테스트' for d in docs)
        class SyntheticSource:
            def search(self, *args, **kwargs): return []
            def fetch(self, article): return article
        store = Store(Path(temp) / 'test.sqlite3')
        store.put(synthetic)
        graph = build_graph(store, SyntheticSource(), index, model(config), config)
        output = graph.invoke({'item': synthetic, 'question': '처음 요청한 형벌과 실제 처분은 같았어?', 'history': []})
        report['graph_nodes'] = list(graph.get_graph().nodes)
        report['answer'] = output['answer']
        report['passed'] = all([report['idempotent'], report['selected_metadata_present'], report['own_body_present'],
                                any(c['verdict'] == '기록과 상충함' and c['evidence'] for c in output['answer']['claims'])])
        # Chroma의 네이티브 핸들이 Windows에서 파일 잠금을 유지하므로 닫는다.
        index.meta._client._system.stop()
        store.db.close()
    report['seconds'] = round(time.monotonic() - started, 2)
    target = ROOT / 'docs' / 'live_smoke_result.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
