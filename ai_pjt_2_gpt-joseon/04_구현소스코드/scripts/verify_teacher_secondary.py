"""이미 수집한 해설만으로 훈장님 답변 정책을 검증한다. 실제 GMS 호출 비용이 발생한다."""
import json
from history_rag.settings import settings, ROOT
from history_rag.storage import Store
from history_rag.index import common_metadata
from history_rag.llm import model, ask_json
from history_rag import prompts
from history_rag.pipeline import validate_answer, validate_passage
from history_rag.teacher import narrative_fields, needs_teacher_repair, apply_teacher_repair
from langchain_core.documents import Document


def main():
    config = settings()
    article = Store().get('aks:E0043666')
    if not article or not article.get('text'):
        raise RuntimeError('검증할 해설을 먼저 실제 수집해야 합니다.')
    evidence = [Document(page_content=article['text'], metadata=common_metadata(article, '웹 해설'))]
    llm = model(config)
    raw = ask_json(llm, prompts.ANSWER, {
        'question': '이괄의 난이 언제 어떤 배경에서 일어났는지 알려줘',
        'claims': ['이괄의 난의 시점과 배경을 설명할 수 있다.'], 'conversation': [], 'is_followup': False,
        'evidence': [{'number': 1, **evidence[0].metadata, 'text': evidence[0].page_content}]})
    if needs_teacher_repair(narrative_fields(raw)):
        raw = apply_teacher_repair(raw, ask_json(llm, prompts.TEACHER_STYLE, narrative_fields(raw)))
    checked = validate_answer(raw, evidence)
    response = validate_passage(checked.get('response'), evidence)
    checks = {'teacher_voice': not needs_teacher_repair(narrative_fields(checked)),
              'response_has_real_quote': bool(response['text'] and response['evidence']),
              'secondary_only': not evidence[0].metadata['is_primary'],
              'no_automatic_primary_refusal': not any(x in response['text'] for x in ['실록 본문', '웹 해설에서는', '제공된 자료'])}
    result = {'question': '이괄의 난 시점·배경', 'checks': checks, 'answer': checked,
              'sources': [{'text': evidence[0].page_content, 'metadata': evidence[0].metadata}]}
    (ROOT / 'docs' / 'teacher_secondary_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(checks, ensure_ascii=False))
    print(response['text'])
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
