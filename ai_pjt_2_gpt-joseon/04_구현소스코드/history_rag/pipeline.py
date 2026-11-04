import re
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from . import prompts
from .llm import ask_json
from .research import retain_selected_metadata, supported_retry_queries, period_scope
from .teacher import narrative_fields, needs_teacher_repair, apply_teacher_repair

VERDICTS = {'기록상 뒷받침됨', '일부만 뒷받침됨', '기록과 상충함', '현재 근거 부족'}


class State(TypedDict, total=False):
    item: dict
    question: str
    history: list
    evidence: list
    resolved_question: str
    answer: dict
    trace: dict
    claims: list
    direct_answer: dict


def normalize(text):
    return re.sub(r'\s+', '', text)


def validate_answer(answer, evidence):
    claims = answer.get('claims', [])
    if not isinstance(claims, list) or not claims:
        return {'summary': '현재 근거 부족', 'claims': [], 'unknowns': ['답변 형식을 확인하지 못했구나. 다시 살펴봐야겠어.']}
    for claim in claims:
        valid = []
        for e in claim.get('evidence', []):
            n, quote = e.get('number'), e.get('quote', '')
            if type(n) is int and 1 <= n <= len(evidence) and isinstance(quote, str) and len(normalize(quote)) >= 6:
                doc = evidence[n - 1]
                if doc.metadata['source_kind'] != '항목 메타데이터' and normalize(quote) in normalize(doc.page_content):
                    valid.append({'number': n, 'quote': quote})
        claim['evidence'] = valid
        if claim.get('verdict') not in VERDICTS or (claim.get('verdict') != '현재 근거 부족' and not valid):
            claim['verdict'] = '현재 근거 부족'
            claim['explanation'] = '이 판단을 뒷받침할 구절을 확인하지 못했구나.'
        if any(word in claim.get('claim', '') for word in ['항상', '모든', '무조건', '언제나', '예외 없이']) and claim.get('verdict') == '기록상 뒷받침됨':
            claim['verdict'] = '현재 근거 부족'
            claim['explanation'] = '이 사례만으로 언제나 그랬다고 단정할 수는 없단다.'
    # 검증 실패 이전의 요약이 화면에 남지 않도록 결과에서 재구성한다.
    answer['summary'] = ' · '.join(dict.fromkeys(c['verdict'] for c in claims))
    return answer


def validate_passage(passage, evidence):
    if not isinstance(passage, dict):
        return {"text": "", "evidence": []}
    checked = validate_answer({"claims": [{"claim": passage.get("text", ""), "verdict": "기록상 뒷받침됨", "evidence": passage.get("evidence", [])}]}, evidence)["claims"][0]
    return {"text": passage.get("text", "") if checked["evidence"] else "", "evidence": checked["evidence"]}


def validate_enrichment(raw, evidence, response=None):
    """덧붙인 이야기에도 본문 인용을 요구하고, 같은 문장 반복은 제거한다."""
    passage = validate_passage(raw, evidence)
    text = re.sub(r'[\W_]+', '', passage['text'])
    prior = re.sub(r'[\W_]+', '', (response or {}).get('text', ''))
    if text and prior and (text in prior or prior in text):
        return {'text': '', 'evidence': []}
    return passage


def prioritize_collected_primary(searched, collected, index, top_k, claim_hits=None):
    """새로 선별해 확보한 사료가 누적된 웹 해설에 밀리지 않게 본문 예산 안에서 우선한다."""
    from langchain_core.documents import Document
    from .index import common_metadata
    from .storage import digest
    metadata = [d for d in searched if d.metadata.get('source_kind') == '항목 메타데이터']
    # 질문의 세부 주장별로 찾은 청크를 먼저 확보한다. 문서 앞부분만 넣으면
    # 후반의 최후/최종 처분을 놓치고 '근거 부족'으로 오판할 수 있다.
    preferred = list(claim_hits or [])
    for article in collected:
        if article.get('source_kind') == '웹 해설' or not article.get('text'):
            continue
        for chunk in index.splitter.split_text(article['text'])[:1]:
            preferred.append(Document(page_content=chunk, metadata=common_metadata(article, article.get('source_kind', '기존 번역'))))
    # 이번 질문에서 선별한 설명 자료도 과거 질문의 누적 자료보다 먼저 넣는다.
    for article in sorted(collected, key=lambda d: (d.get('collection') == '한국어 위키백과 연도별 해설', not d['id'].startswith('aks:'))):
        if article.get('source_kind') != '웹 해설' or not article.get('text'):
            continue
        for chunk in index.splitter.split_text(article['text'])[:2]:
            preferred.append(Document(page_content=chunk, metadata=common_metadata(article, '웹 해설')))
    bodies = preferred + [d for d in searched if d.metadata.get('source_kind') != '항목 메타데이터']
    seen, merged = set(), []
    for doc in bodies:
        key = (doc.metadata.get('article_id'), doc.metadata.get('source_kind'), digest(doc.page_content))
        if key not in seen:
            merged.append(doc)
            seen.add(key)
    return metadata + merged[:top_k]


def build_graph(store, source, index, llm, config, progress=lambda message: None):
    from .timeline import load_periods, match_periods
    from .web_context import WebContext
    from .transcriptions import TranscriptionClient
    from .encyclopedia import Encyclopedia

    def retrieve(state):
        progress("질문 해석 · 사건과 날짜 단서 찾기")
        from .chronology import chronology_periods, chronology_evidence, chronology_answer
        known = chronology_periods(state['question'], state.get('history', []), load_periods())
        if known:
            evidence = chronology_evidence(known)
            return {'resolved_question': state['question'], 'claims': [], 'evidence': evidence,
                'direct_answer': chronology_answer(known, evidence),
                'trace': {'queries': [], 'records': [], 'bodies': [], 'failed_ids': [], 'errors': [],
                          'periods': known, 'method': '검증된 왕력 표의 연도/왕 관계 대조'}}
        item = state.get("item")
        query = ask_json(llm, prompts.QUERY, {
            "selected_period": {k: item.get(k) for k in ["id", "title", "king", "year"]} if item else None,
            "question": state["question"], "history": state.get("history", [])[-config["history_turns"] * 2:]})
        resolved = query.get("resolved_question") or state["question"]
        periods = load_periods()
        # 왕 이름만 나온 질문을 그 왕의 첫해로 좁히면 다른 재위년의 사건이 사라진다.
        selected_periods, anchor, directory, king_directory = period_scope(periods, resolved, query.get('king'), query.get('year_hint'), item)
        candidates, errors = {}, []
        progress("인터넷 검색 · 실록 기사 후보 검색")
        for term in query.get("queries", [])[:3]:
            if not isinstance(term, str) or not term.strip():
                continue
            try:
                kwargs = {"directory": directory} if directory else {}
                for a in source.search(term, **kwargs):
                    candidates[a["id"]] = a
            except RuntimeError:
                errors.append("공식 사료 후보 검색 실패")
        sjw_period = bool(anchor and anchor.get('year', 0) >= 1623) or any(
            p['king'] == query.get('king') and p['year'] >= 1623 for p in periods)
        if sjw_period and config.get('search_sjw', True):
            try:
                terms = query.get('queries', [])
                if terms:
                    for a in source.search(terms[0], section='ST_BD'):
                        candidates[a['id']] = a
            except RuntimeError:
                errors.append('승정원일기 후보 검색 실패')
        web = WebContext(source) if config.get("enable_web_context") else None
        encyclopedia = Encyclopedia(source)
        if web:
            try:
                for a in web.search(query.get("web_query") or resolved, refresh=getattr(source, 'refresh', False)):
                    candidates[a["id"]] = a
            except (RuntimeError, ValueError):
                errors.append("웹 해설 검색 실패")
        if config.get('enable_encyclopedia', True):
            try:
                for a in encyclopedia.search(query.get('topic_query') or query.get('web_query') or resolved, refresh=getattr(source, 'refresh', False)):
                    candidates[a['id']] = a
            except (RuntimeError, ValueError):
                errors.append('백과사전 보완 검색 실패')
        selected = ask_json(llm, prompts.SELECT, {"question": resolved, "limit": config["selected_count"], "candidates": [
            {k: a.get(k, "") for k in ["id", "title", "collection", "date_original", "source_kind"]} |
            {"snippet": a.get("snippet", "") if a.get("rights_status") == "permitted" else "공식 API 후보: 제목과 날짜로 관련성 확인"}
            for a in candidates.values()]}) if candidates else {"selected": []}
        choices = [(item, "선택 기사 자체")] if item and item.get("item_kind") != "royal_year" else []
        for row in selected.get("selected", [])[:config["selected_count"]]:
            if row.get("id") in candidates and (not item or row["id"] != item["id"]):
                choices.append((candidates[row["id"]], row.get("reason", "후보 선별")))
        progress("관련 기록 본문 확보 · 색인 · 두 컬렉션 검색")
        failures, collected, bodies = [], [], []
        year_document_status = 'not_selected'
        if item and item.get('item_kind') == 'royal_year':
            # 선택 연도의 설명 문서는 사건별 후보 선별과 별도로 확보한다.
            # 서기년 해설은 전 세계 연표이며 해당 왕의 실록 본문이 아니다.
            try:
                year_doc = (web or WebContext(source)).period_document(item, refresh=getattr(source, 'refresh', False))
                if year_doc:
                    index.index_body(item['id'], year_doc)
                    store.link(item['id'], year_doc['id'], '선택 왕력 연도에 대응하는 서기년 설명 문서')
                    collected.append(year_doc['id'])
                    bodies.append(year_doc)
                    year_document_status = 'indexed'
                else:
                    year_document_status = 'unavailable'
                    errors.append('선택 연도 설명 문서는 아직 확보하지 못했구나')
            except (RuntimeError, ValueError):
                year_document_status = 'unavailable'
                errors.append('선택 연도의 설명 문서 수집 실패')
        for article, reason in choices:
            try:
                if article['id'].startswith('aks:'):
                    doc = encyclopedia.fetch(article, refresh=getattr(source, 'refresh', False))
                else:
                    doc = web.fetch(article, refresh=getattr(source, 'refresh', False)) if article["id"].startswith("wiki:") and web else source.fetch(article)
                if doc.get("text"):
                    scope_id = anchor["id"] if anchor else "free_questions"
                    index.index_body(scope_id, doc)
                    store.link(scope_id, doc["id"], reason)
                    collected.append(doc["id"])
                    bodies.append(doc)
                else:
                    failures.append(article["id"])
            except RuntimeError:
                failures.append(article["id"])
                if config.get('enable_transcriptions', True) and article.get('collection', '').find('실록') >= 0:
                    period = next((p for p in periods if p.get('book_id') and article['id'].startswith(p['id'] + '_')), None)
                    try:
                        alternate = TranscriptionClient(source).fetch_for(article, period)
                        if alternate:
                            scope_id = period['id']
                            index.index_body(scope_id, alternate)
                            store.link(scope_id, alternate['id'], alternate['relation_basis'])
                            collected.append(alternate['id'])
                            bodies.append(alternate)
                    except (RuntimeError, ValueError):
                        errors.append('한문 전사본 확보 실패')
        # 해설에서 끝내지 않고 본문에 실제 있는 단서를 사용해 최대 두 검색어만 보완한다.
        retry_queries = []
        if bodies and not any(d.get('is_primary', d.get('source_kind') != '웹 해설') for d in bodies):
            progress('이 단서를 따라 다른 기록도 살펴보자꾸나…')
            try:
                plan = ask_json(llm, prompts.RESEARCH, {'question': resolved, 'documents': [
                    {'title': d['title'], 'text': d['text'][:10000]} for d in bodies[:2]]})
                retry_queries = supported_retry_queries(plan, bodies, config.get('primary_retry_queries', 2))
                attempted = {a['id'] for a, _ in choices}
                retried = 0
                for term in retry_queries:
                    extra = source.search(term, **({'directory': king_directory} if king_directory else {}))
                    for a in extra:
                        candidates[a['id']] = a
                    selected_retry = ask_json(llm, prompts.SELECT, {'question': resolved, 'limit': 2,
                        'candidates': [{k: a.get(k, '') for k in ['id', 'title', 'collection', 'date_original']}
                                       for a in extra if a['id'] not in attempted]}) if extra else {'selected': []}
                    for row in selected_retry.get('selected', [])[:2]:
                        article = next((a for a in extra if a['id'] == row.get('id')), None)
                        if not article or article['id'] in attempted or retried >= 2:
                            continue
                        attempted.add(article['id'])
                        retried += 1
                        choices.append((article, '해설 본문 단서로 재탐색'))
                        try:
                            doc = source.fetch(article)
                        except RuntimeError:
                            period = next((p for p in periods if p.get('book_id') and article['id'].startswith(p['id'] + '_')), None)
                            doc = TranscriptionClient(source).fetch_for(article, period) if config.get('enable_transcriptions', True) and '실록' in article.get('collection', '') else None
                        if doc and doc.get('text'):
                            scope = next((p['id'] for p in periods if p.get('book_id') and article['id'].startswith(p['id'] + '_')), anchor['id'] if anchor else 'free_questions')
                            index.index_body(scope, doc)
                            store.link(scope, doc['id'], '해설 본문 단서로 재탐색')
                            bodies.append(doc)
                            collected.append(doc['id'])
                    if any(d.get('is_primary', d.get('source_kind') != '웹 해설') for d in bodies):
                        break
            except (RuntimeError, ValueError):
                errors.append('추가로 살핀 사료 본문은 확보하지 못했구나')
        claims = [c for c in query.get("claims", []) if isinstance(c, str) and not any(x in c for x in ["해야 한다", "필요하다", "확인할 것"])]
        evidence = index.retrieve(anchor, resolved, scoped=bool(item and item.get("item_kind") != "royal_year"))
        claim_hits = []
        for claim in claims[:3]:
            # 공통 질문뿐 아니라 각 세부 주장으로 검색하여 결말·계기 등의 누락을 줄인다.
            if index.counts()['body_chunks']:
                claim_hits.extend(index.body.similarity_search(claim, k=2))
        evidence = prioritize_collected_primary(evidence, bodies, index, config['top_k'], claim_hits)
        evidence = retain_selected_metadata(evidence, item)
        for period in selected_periods[1:]:
            from langchain_core.documents import Document
            from .index import metadata_text, common_metadata
            evidence.append(Document(page_content=metadata_text(period), metadata=common_metadata(period, "항목 메타데이터")))
        return {"resolved_question": resolved, "claims": claims or [resolved], "evidence": evidence,
                "trace": {"queries": query.get("queries", []), "web_query": query.get("web_query", resolved), "candidate_ids": list(candidates),
                          "selected_ids": [a["id"] for a, _ in choices], "collected_ids": collected,
                          "failed_ids": failures, "errors": errors,
                          "periods": [{k: p.get(k) for k in ["id", "title", "year", "url"]} for p in selected_periods],
                          "records": [a for a in candidates.values() if a.get("source_kind") != "웹 해설"],
                          "bodies": bodies, 'retry_queries': retry_queries, 'year_document_status': year_document_status}}

    def generate(state):
        if state.get('direct_answer'):
            return {'answer': state['direct_answer']}
        progress("근거를 확인하며 답변 · 쉬운 해설 작성")
        history = state.get('history', [])[-config['history_turns'] * 2:]
        payload = {"question": state['question'], 'resolved_question': state["resolved_question"],
                   'conversation': history, 'is_followup': any(m.get('role') == 'assistant' for m in history),
                   "claims": state.get("claims", []), "evidence": [
            {"number": i, **d.metadata, "text": d.page_content} for i, d in enumerate(state["evidence"], 1)]}
        raw = ask_json(llm, prompts.ANSWER, payload)
        # 불확실/상충 판단이 있으면 다른 출처의 근거도 다시 대조하고
        # 본문·주장별 판단·미확인 사항을 한 번에 정합하게 다시 작성한다.
        tentative = validate_answer(raw, state['evidence'])
        if any(c.get('verdict') != '기록상 뒷받침됨' for c in tentative.get('claims', [])):
            progress('부족한 대목은 다른 자료에서도 찾아보자꾸나…')
            plan = ask_json(llm, prompts.SUPPLEMENT, {'question': state['resolved_question'],
                'claims': tentative.get('claims', []), 'history': history})
            added = []
            for term in plan.get('queries', [])[:2]:
                if not isinstance(term, str) or not term.strip() or len(term) > 100:
                    continue
                found = []
                for adapter in [Encyclopedia(source), WebContext(source)]:
                    try:
                        candidates = adapter.search(term)
                        for candidate in candidates[:1]:
                            doc = adapter.fetch(candidate)
                            if doc.get('text'):
                                scope = state['item']['id'] if state.get('item') else 'free_questions'
                                index.index_body(scope, doc)
                                added.append(doc)
                                found.append(doc)
                    except (RuntimeError, ValueError):
                        continue
                if found:
                    break
            if added:
                supplemental = []
                for claim in state.get('claims', [])[:3]:
                    supplemental.extend(index.body.similarity_search(claim, k=2))
                state['evidence'] = prioritize_collected_primary(state['evidence'], added, index, config['top_k'], supplemental)
                state['trace']['bodies'].extend(added)
                state['trace']['supplement_queries'] = plan.get('queries', [])[:2]
                payload['evidence'] = [{'number': i, **d.metadata, 'text': d.page_content}
                                       for i, d in enumerate(state['evidence'], 1)]
            progress('설명과 확인 결과가 서로 맞는지 다시 살펴보자꾸나…')
            raw = ask_json(llm, prompts.ANSWER + '\n' + prompts.CONSISTENCY, {
                **payload, 'previous_answer': {'claims': [{k: c.get(k) for k in ['claim', 'verdict', 'explanation']} for c in tentative.get('claims', [])], 'response_text': tentative.get('response', {}).get('text', '')}})
        if needs_teacher_repair(narrative_fields(raw)):
            raw = apply_teacher_repair(raw, ask_json(llm, prompts.TEACHER_STYLE, narrative_fields(raw)))
            if needs_teacher_repair(narrative_fields(raw)):
                raise RuntimeError('훈장님 말투 교정을 완료하지 못했습니다.')
        answer = validate_answer(raw, state["evidence"])
        expected = state.get("claims") or [state["resolved_question"]]
        by_claim = {c.get("claim"): c for c in answer.get("claims", [])}
        answer["claims"] = [by_claim.get(c, {"claim": c, "verdict": "현재 근거 부족",
                            "explanation": "이 부분은 아직 정확히 확인하지 못했구나.", "evidence": []}) for c in expected if isinstance(c, str)]
        answer["summary"] = " · ".join(dict.fromkeys(c["verdict"] for c in answer["claims"])) or "현재 근거 부족"
        for field in ["response", "interpretation"]:
            answer[field] = validate_passage(raw.get(field), state["evidence"])
        answer['interpretation'] = validate_enrichment(raw.get('interpretation'), state['evidence'], answer['response'])
        answer['aside'] = validate_enrichment(raw.get('aside'), state['evidence'], answer['response'])
        suggestions = raw.get('follow_up_questions', [])
        answer['follow_up_questions'] = [q.strip() for q in suggestions if isinstance(q, str) and 0 < len(q.strip()) <= 100 and not any(x in q for x in ['원문을 확인', '더 찾아', '번역해', '원문을 찾아'])][:2] if isinstance(suggestions, list) else []
        answer['ai_translation'] = validate_passage(raw.get('ai_translation'), state['evidence'])
        if not any(state['evidence'][e['number'] - 1].metadata.get('source_kind') == '한문 원문 전사본' for e in answer['ai_translation']['evidence']):
            answer['ai_translation'] = {'text': '', 'evidence': []}
        cited = {e['number'] for c in answer['claims'] for e in c.get('evidence', [])}
        cited.update(e['number'] for field in ['response', 'interpretation', 'aside', 'ai_translation'] for e in answer[field].get('evidence', []))
        primary_numbers = {i for i, d in enumerate(state['evidence'], 1) if d.metadata.get('is_primary', True) and d.metadata['source_kind'] != '항목 메타데이터'}
        answer['has_primary_evidence'] = bool(cited & primary_numbers)
        answer['evidence_scope'] = '인용한 기록과 함께 읽어보렴' if cited else '아직 확인할 자료가 부족하구나'
        answer['source_types'] = sorted({state['evidence'][n-1].metadata['source_kind'] for n in cited})
        answer['style_version'] = 'teacher-v2'
        answer['summary'] = ' · '.join(dict.fromkeys(c['verdict'] for c in answer['claims'])) or '현재 근거 부족'
        return {"answer": answer, 'evidence': state['evidence'], 'trace': state['trace']}

    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
