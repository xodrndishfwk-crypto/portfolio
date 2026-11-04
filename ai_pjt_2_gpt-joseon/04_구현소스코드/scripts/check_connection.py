"""키·응답·오류 전문을 출력하지 않는 소량 GMS 검증."""
from history_rag.settings import settings
from history_rag.llm import model, embeddings


def main():
    config = settings()
    for name, action in [('chat', lambda: bool(model(config).invoke('Reply OK.').content)),
                         ('embedding_dimensions', lambda: len(embeddings(config).embed_query('연결 검증')))]:
        try:
            print(name, action())
        except Exception as e:
            print(name, 'FAILED', type(e).__name__)


if __name__ == '__main__':
    main()
