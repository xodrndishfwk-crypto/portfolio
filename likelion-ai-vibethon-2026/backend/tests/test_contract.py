import os
import sys
import unittest


BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import app
from schemas.answer import AnswerRequest
from schemas.question import QuestionRequest
from services.answer_service import normalized_text, polish_answer
from services.question_service import transform_question


class ApiContractTest(unittest.TestCase):
    def setUp(self):
        self.previous_keys = {
            key: os.environ.pop(key, None)
            for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")
        }

    def tearDown(self):
        for key, value in self.previous_keys.items():
            if value is not None:
                os.environ[key] = value

    def test_existing_routes_are_preserved(self):
        paths = set(app.openapi()["paths"])
        self.assertIn("/", paths)
        self.assertIn("/api/health", paths)
        self.assertIn("/api/questions/transform", paths)
        self.assertIn("/api/answers/polish", paths)
        self.assertIn("/api/families/{family_id}/invite", paths)
        self.assertIn("/api/families/{family_id}/invites", paths)

    def test_question_local_fallback_contract(self):
        result = transform_question(
            QuestionRequest(worry="면접에서 계속 떨어져서 힘들어", emotion="지침", mode="stealth")
        )
        self.assertEqual(result["source"], "local")
        self.assertEqual(result["mode"], "stealth")
        self.assertEqual(result["emotion"], "지침")
        self.assertEqual(len(result["questions"]), 5)
        self.assertIn(result["target_question"], result["questions"])
        self.assertEqual(result["question"], result["questions"][0])

    def test_direct_question_contains_only_the_target(self):
        result = transform_question(
            QuestionRequest(worry="진로를 어떻게 정했는지 궁금해", emotion="불안", mode="direct")
        )
        self.assertEqual(result["questions"], [result["target_question"]])

    def test_answer_local_fallback_contract(self):
        original = "나도 처음엔 막막했지만 그냥 버텼어"
        result = polish_answer(
            AnswerRequest(answer=original, question="실패했을 때 어떻게 견뎠나요?")
        )
        self.assertEqual(result["source"], "local")
        self.assertEqual(result["original"], original)
        self.assertTrue(result["polished"])
        self.assertTrue(result["recommendation_reason"])
        self.assertEqual(result["tone"], "warm")
        self.assertNotIn(normalized_text(original), normalized_text(result["polished"]))

    def test_answer_tone_changes_local_suggestion(self):
        original = "그렇게 하면 안 돼. 정신 차리고 제대로 해."
        warm = polish_answer(AnswerRequest(answer=original, question="실패했을 때 어떻게 견뎠나요?", tone="warm"))
        practical = polish_answer(AnswerRequest(answer=original, question="실패했을 때 어떻게 견뎠나요?", tone="practical"))
        self.assertNotEqual(warm["polished"], practical["polished"])
        self.assertNotIn(normalized_text(original), normalized_text(warm["polished"]))


if __name__ == "__main__":
    unittest.main()
