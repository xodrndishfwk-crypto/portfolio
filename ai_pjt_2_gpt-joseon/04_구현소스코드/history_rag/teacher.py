"""인용문은 보존하고 훈장님의 서술 말투만 검사한다."""
import re
from copy import deepcopy


def narrative_fields(answer):
    result = {k: answer[k].get('text', '') if isinstance(answer.get(k), dict) else '' for k in ['response', 'interpretation', 'aside']}
    result['explanations'] = [c.get('explanation', '') for c in answer.get('claims') or [] if isinstance(c, dict)]
    result['unknowns'] = answer.get('unknowns') or []
    result['follow_up_questions'] = answer.get('follow_up_questions') or []
    return result


def needs_teacher_repair(fields):
    texts = []
    for value in fields.values():
        texts.extend(value if isinstance(value, list) else [value])
    for text in texts:
        if not isinstance(text, str):
            continue
        text = re.sub(r'“[^”]*”|「[^」]*」|"[^"]*"', '', text)
        if re.search(r'(?:[가-힣]*(?:했|났|렸|졌|됐|였|있|없|겠|었|았)소|그렇소|같소|맞소|하오|이오|아니오|보시오|주시오|하였소이다)(?=[.!?…\s]|$)', text):
            return True
        if re.search(r'제공된\s*(?:웹\s*해설|자료)|웹\s*해설에서는|실록\s*본문.{0,15}(?:미확보|확인하지 못|확보하지 못)', text):
            return True
    return False


def apply_teacher_repair(answer, fields):
    """수정 결과에서 서술문만 반영한다. 근거 번호·인용문·판정·주장·번역은 바꿀 수 없다."""
    answer = deepcopy(answer)
    for key in ['response', 'interpretation', 'aside']:
        if isinstance(fields.get(key), str) and isinstance(answer.get(key), dict):
            answer[key]['text'] = fields[key]
    for claim, text in zip(answer.get('claims', []), fields.get('explanations', [])):
        if isinstance(text, str):
            claim['explanation'] = text
    for key in ['unknowns', 'follow_up_questions']:
        value = fields.get(key)
        if isinstance(value, list) and len(value) == len(answer.get(key, [])) and all(isinstance(t, str) for t in value):
            answer[key] = value
    return answer
