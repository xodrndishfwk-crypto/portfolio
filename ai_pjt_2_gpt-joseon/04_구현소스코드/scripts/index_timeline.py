from history_rag.settings import settings
from history_rag.timeline import load_periods
from history_rag.index import Index
from history_rag.llm import embeddings


def main():
    config = settings()
    periods = load_periods()
    if not periods:
        raise SystemExit('먼저 python -m scripts.prepare_timeline 실행')
    index = Index(embeddings(config), config)
    print('new_period_chunks', index.index_metadata(periods), flush=True)
    print(index.counts())


if __name__ == '__main__':
    main()
