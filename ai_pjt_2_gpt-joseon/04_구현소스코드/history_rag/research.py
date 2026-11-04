"""출처에 있는 단서로만 재탐색하고 원래 선택한 시기를 보존한다."""
import re
from langchain_core.documents import Document
from .index import metadata_text, common_metadata


def period_scope(periods, question, king=None, year=None, selected=None):
    from .timeline import match_periods
    matches = match_periods(periods, question, king, year)
    has_year = bool(year or re.search(r'(?<!\d)1[3-9]\d{2}|(?:즉위|\d+)년', question))
    selection_applies = selected and (not king or selected.get('king') == king)
    chosen = (matches[:4] if has_year else []) or ([selected] if selection_applies and selected.get('item_kind') == 'royal_year' else [])
    anchor = chosen[0] if chosen else (selected if selection_applies else None)
    king_directory = next((p.get('book_id') for p in periods if p['king'] == king and p.get('book_id')), None)
    directory = (anchor.get('id') if anchor and anchor.get('book_id') else None) or king_directory
    return chosen, anchor, directory, king_directory


def retain_selected_metadata(evidence, selected):
    if not selected:
        return evidence
    if any(d.metadata.get('article_id') == selected['id'] and
           d.metadata.get('source_kind') == '항목 메타데이터' for d in evidence):
        return evidence
    return [Document(page_content=metadata_text(selected),
                     metadata=common_metadata(selected, '항목 메타데이터'))] + evidence


def supported_retry_queries(plan, documents, limit=2):
    """LLM이 만든 연도·검색어를 확정 사실로 사용하지 않는다. 인용 단서는 실제 본문에 있어야 한다."""
    result, seen = [], set()
    for row in plan.get('searches', []) if isinstance(plan, dict) else []:
        if not isinstance(row, dict):
            continue
        phrase, quote = row.get('query', ''), row.get('quote', '')
        if not isinstance(phrase, str) or not 1 <= len(phrase.strip()) <= 60:
            continue
        if not isinstance(quote, str) or len(quote.strip()) < 6:
            continue
        if not any(quote in d.get('text', '') for d in documents):
            continue
        phrase = phrase.strip()
        if phrase not in seen:
            result.append(phrase)
            seen.add(phrase)
        if len(result) >= limit:
            break
    return result


def collection_status(answer):
    """검색 작업의 완료와 주장의 사실 확인을 구분한다."""
    if answer.get('has_primary_evidence'):
        return '이야기와 기록을 함께 준비했단다'
    if answer.get('source_types'):
        return '찾아낸 자료로 이야기를 정리했단다'
    return '아직 답을 뒷받침할 자료가 부족하구나'
