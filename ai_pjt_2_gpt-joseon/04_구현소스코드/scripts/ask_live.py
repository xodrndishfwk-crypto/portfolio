"""실제 자유 질문 통합 검증. 응답은 로컬 data/에 기록."""
import argparse
import json
import time
from history_rag.settings import settings, ROOT
from history_rag.storage import Store
from history_rag.sources import SourceClient
from history_rag.index import Index
from history_rag.llm import model, embeddings
from history_rag.pipeline import build_graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('question', nargs='?', default='임진왜란 때 선조는 언제 의주로 피란 갔어?')
    parser.add_argument('--follow-up', default='')
    args = parser.parse_args()
    config, store = settings(), Store()
    index = Index(embeddings(config), config)
    graph = build_graph(store, SourceClient(store, config), index, model(config), config, lambda msg: print(msg, flush=True))
    started = time.monotonic()
    output = graph.invoke({'item': None, 'question': args.question, 'history': []})
    report = {'question': args.question, 'seconds': round(time.monotonic() - started, 2),
              'answer': output['answer'], 'sources': [d.metadata for d in output['evidence']],
              'periods': output['trace'].get('periods', []), 'queries': output['trace']['queries'],
              'candidate_count': len(output['trace']['candidate_ids']), 'selected_ids': output['trace']['selected_ids'],
              'collected_ids': output['trace']['collected_ids'], 'failed_ids': output['trace']['failed_ids'],
              'errors': output['trace'].get('errors', []), 'counts': index.counts()}
    (ROOT / 'data' / 'free_question_result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.follow_up:
        next_started = time.monotonic()
        follow = graph.invoke({'item': None, 'question': args.follow_up, 'history': [
            {'role': 'user', 'content': args.question},
            {'role': 'assistant', 'content': json.dumps(output['answer'], ensure_ascii=False)}]})
        report['follow_up'] = {'question': args.follow_up, 'seconds': round(time.monotonic() - next_started, 2), 'answer': follow['answer']}
        (ROOT / 'data' / 'answer_style_result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ['sources']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
