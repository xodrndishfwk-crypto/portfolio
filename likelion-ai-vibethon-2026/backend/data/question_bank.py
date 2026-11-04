import json
import random
import re
from pathlib import Path


LIBRARY_PATH = Path(__file__).with_name("question_library.json")


def _load_library() -> dict:
    with LIBRARY_PATH.open(encoding="utf-8") as file:
        library = json.load(file)
    if not isinstance(library.get("categories"), list):
        raise ValueError("question_library.json의 categories 형식이 올바르지 않습니다.")
    return library


QUESTION_LIBRARY = _load_library()
QUESTION_POOLS = {
    category["id"]: {
        "label": category.get("label", category["id"]),
        "keywords": tuple(category["keywords"]),
        "questions": list(category["questions"]),
    }
    for category in QUESTION_LIBRARY["categories"]
}
GENERAL_QUESTIONS = list(QUESTION_LIBRARY["general_questions"])
LIGHT_KEYWORDS = tuple(QUESTION_LIBRARY["light_keywords"])
LIGHT_QUESTIONS = list(QUESTION_LIBRARY["light_questions"])
LIGHT_TARGET_RULES = [
    (tuple(rule["keywords"]), rule["question"])
    for rule in QUESTION_LIBRARY["light_target_rules"]
]
AI_QUESTION_EXAMPLES = list(QUESTION_LIBRARY.get("ai_examples", []))


ALL_SYSTEM_QUESTIONS = list(
    dict.fromkeys(
        question
        for group in [
            *(pool["questions"] for pool in QUESTION_POOLS.values()),
            GENERAL_QUESTIONS,
            LIGHT_QUESTIONS,
        ]
        for question in group
    )
)


def select_question_examples(text: str, emotion: str, limit: int = 6) -> list[dict]:
    """입력 주제와 가까운 예시를 우선하되 매번 일부 구성을 바꿔 복제를 방지한다."""
    normalized = re.sub(r"\s+", " ", f"{text} {emotion}").lower()
    ranked = sorted(
        AI_QUESTION_EXAMPLES,
        key=lambda example: sum(
            keyword in normalized
            for pool in QUESTION_POOLS.values()
            for keyword in pool["keywords"]
            if keyword in example["worry"] or keyword in example["target_question"]
        ),
        reverse=True,
    )
    seed = sum(ord(character) for character in normalized)
    rng = random.Random(seed)
    if len(ranked) > 2:
        tail = ranked[2:]
        rng.shuffle(tail)
        ranked = ranked[:2] + tail
    return ranked[:limit]
