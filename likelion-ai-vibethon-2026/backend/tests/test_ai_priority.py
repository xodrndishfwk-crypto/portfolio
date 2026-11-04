import os
import sys
import unittest
from unittest.mock import patch


BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from data.question_bank import ALL_SYSTEM_QUESTIONS, AI_QUESTION_EXAMPLES
from schemas.answer import AnswerRequest
from schemas.question import QuestionRequest
from services.answer_service import polish_answer
from services.openai_client import request_structured_output
from services.question_service import transform_question


class AiPriorityTest(unittest.TestCase):
    def request(self):
        return request_structured_output(
            instructions="test",
            input_text="test",
            schema_name="test_schema",
            schema={"type": "object", "properties": {}, "additionalProperties": False},
        )

    def test_openai_is_called_before_gemini(self):
        env = {
            "OPENAI_API_KEY": "openai-test",
            "GEMINI_API_KEY": "gemini-test",
            "ENABLE_GEMINI_FALLBACK": "true",
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("services.openai_client._call_openai", return_value={"result": "openai"}) as openai_call, \
             patch("services.openai_client._call_gemini", return_value={"result": "gemini"}) as gemini_call:
            result = self.request()

        self.assertEqual(result["_provider"], "openai")
        openai_call.assert_called_once()
        gemini_call.assert_not_called()

    def test_gemini_is_only_used_after_openai_failure(self):
        env = {
            "OPENAI_API_KEY": "openai-test",
            "GEMINI_API_KEY": "gemini-test",
            "ENABLE_GEMINI_FALLBACK": "true",
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("services.openai_client._call_openai", return_value=None) as openai_call, \
             patch("services.openai_client._call_gemini", return_value={"result": "gemini"}) as gemini_call:
            result = self.request()

        self.assertEqual(result["_provider"], "gemini")
        openai_call.assert_called_once()
        gemini_call.assert_called_once()

    def test_question_library_is_large_and_unique(self):
        self.assertGreaterEqual(len(ALL_SYSTEM_QUESTIONS), 120)
        self.assertEqual(len(ALL_SYSTEM_QUESTIONS), len(set(ALL_SYSTEM_QUESTIONS)))
        self.assertGreaterEqual(len(AI_QUESTION_EXAMPLES), 8)

    def test_question_transform_keeps_openai_source(self):
        ai_result = {
            "target_question": "결과가 뜻대로 되지 않을 때 다시 도전할 용기를 어떻게 얻으셨나요?",
            "decoy_questions": [
                "어린 시절 가장 기다려졌던 계절 행사는 무엇이었나요?",
                "학창 시절 친구들과 가장 많이 웃었던 순간은 언제였나요?",
                "시간 가는 줄 모르고 즐겼던 취미나 활동이 있으셨나요?",
                "가족과 다시 함께 먹고 싶은 추억의 음식은 무엇인가요?",
            ],
            "intent_preserved": True,
            "privacy_safe": True,
            "_provider": "openai",
        }
        with patch("services.question_service.request_structured_output", return_value=ai_result):
            result = transform_question(
                QuestionRequest(worry="면접에서 계속 떨어져 자신감이 없어요.", emotion="지침", mode="stealth")
            )

        self.assertEqual(result["source"], "openai")
        self.assertEqual(len(result["questions"]), 5)
        self.assertIn(result["target_question"], result["questions"])

    def test_answer_polish_keeps_openai_source(self):
        ai_result = {
            "polished": "나도 다시 실패할까 봐 겁이 났단다. 그래서 하루에 한 가지씩 다시 시도하며 마음을 추슬렀어.",
            "recommendation_reason": "원문의 두려움과 작은 실천을 보존하면서 따뜻한 회고의 흐름으로 정리했어요.",
            "factual_fidelity": True,
            "_provider": "openai",
        }
        with patch("services.answer_service.request_structured_output", return_value=ai_result):
            result = polish_answer(
                AnswerRequest(
                    question="실패가 계속될 때 어떻게 다시 움직이셨나요?",
                    answer="나도 겁났지만 하루에 하나씩 다시 해봤어.",
                    tone="warm",
                )
            )

        self.assertEqual(result["source"], "openai")
        self.assertEqual(result["polished"], ai_result["polished"])


if __name__ == "__main__":
    unittest.main()
