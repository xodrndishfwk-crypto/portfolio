import os
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models import Base


class FamilyFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_ai_keys = {
            key: os.environ.pop(key, None)
            for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY")
        }
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()
        for key, value in cls.saved_ai_keys.items():
            if value is not None:
                os.environ[key] = value

    def register_and_login(self, email, name):
        register = self.client.post(
            "/api/auth/register",
            json={"email": email, "password": "pass1234", "name": name},
        )
        self.assertEqual(register.status_code, 201, register.text)
        login = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "pass1234"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()

    @staticmethod
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    def test_complete_family_question_answer_flow(self):
        child = self.register_and_login("child@example.com", "자녀")
        parent = self.register_and_login("parent@example.com", "부모")
        outsider = self.register_and_login("outsider@example.com", "외부인")

        child_headers = self.auth(child["access_token"])
        parent_headers = self.auth(parent["access_token"])
        outsider_headers = self.auth(outsider["access_token"])

        created = self.client.post(
            "/api/families",
            headers=child_headers,
            json={"name": "테스트 가족", "role": "child"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        family_id = created.json()["id"]

        invite = self.client.post("/api/families/invites", headers=child_headers)
        self.assertEqual(invite.status_code, 200, invite.text)
        joined = self.client.post(
            "/api/families/join",
            headers=parent_headers,
            json={"invite_code": invite.json()["invite_code"], "role": "parent"},
        )
        self.assertEqual(joined.status_code, 200, joined.text)

        delivery = self.client.post(
            "/api/questions/deliveries",
            headers=child_headers,
            json={
                "family_id": family_id,
                "emotion": "불안",
                "worry": "면접에서 계속 떨어져서 자신감이 없어요.",
                "mode": "direct",
            },
        )
        self.assertEqual(delivery.status_code, 201, delivery.text)
        delivery_data = delivery.json()
        self.assertEqual(len(delivery_data["questions"]), 1)

        pending = self.client.get(
            f"/api/questions/deliveries?family_id={family_id}&status=pending",
            headers=parent_headers,
        )
        self.assertEqual(pending.status_code, 200, pending.text)
        self.assertIn(delivery_data["id"], [item["id"] for item in pending.json()])


        answer = self.client.post(
            f"/api/answers/deliveries/{delivery_data['id']}",
            headers=parent_headers,
            json={
                "question": delivery_data["questions"][0],
                "answer": "나도 처음에는 막막했지만 하루씩 준비했어.",
            },
        )
        self.assertEqual(answer.status_code, 201, answer.text)
        answer_id = answer.json()["id"]

        library = self.client.get(f"/api/answers?family_id={family_id}", headers=child_headers)
        self.assertEqual(library.status_code, 200, library.text)
        self.assertEqual(len(library.json()), 1)

        denied = self.client.get(f"/api/answers?family_id={family_id}", headers=outsider_headers)
        self.assertEqual(denied.status_code, 403, denied.text)

        reaction = self.client.post(
            f"/api/answers/{answer_id}/reactions",
            headers=child_headers,
            json={"reaction_type": "thanks"},
        )
        self.assertEqual(reaction.status_code, 200, reaction.text)

        updated_library = self.client.get(f"/api/answers?family_id={family_id}", headers=child_headers)
        self.assertEqual(updated_library.json()[0]["thanks_count"], 1)

    def test_detailed_roles_restore_family_invite_and_final_answer(self):
        child = self.register_and_login("hero-child@example.com", "가입 이름")
        parent = self.register_and_login("hero-parent@example.com", "가입 이름")
        child_headers = self.auth(child["access_token"])
        parent_headers = self.auth(parent["access_token"])

        created = self.client.post(
            "/api/families",
            headers=child_headers,
            json={"name": "영웅 가족", "role": "son", "nickname": "씩씩이"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        family_id = created.json()["id"]
        self.assertEqual(created.json()["members"][0]["name"], "씩씩이")

        empty_invite = self.client.get(f"/api/families/{family_id}/invite", headers=child_headers)
        self.assertEqual(empty_invite.status_code, 200, empty_invite.text)
        self.assertIsNone(empty_invite.json())
        invite = self.client.post(f"/api/families/{family_id}/invites", headers=child_headers)
        self.assertEqual(invite.status_code, 200, invite.text)
        active_invite = self.client.get(f"/api/families/{family_id}/invite", headers=child_headers)
        self.assertEqual(active_invite.json()["invite_code"], invite.json()["invite_code"])

        joined = self.client.post(
            "/api/families/join",
            headers=parent_headers,
            json={"invite_code": invite.json()["invite_code"], "role": "mother", "nickname": "다정한 엄마"},
        )
        self.assertEqual(joined.status_code, 200, joined.text)
        self.assertEqual({member["role"] for member in joined.json()["members"]}, {"son", "mother"})

        restored = self.client.post(
            "/api/auth/login",
            json={"email": "hero-child@example.com", "password": "pass1234"},
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["family"]["id"], family_id)

        delivery = self.client.post(
            "/api/questions/deliveries",
            headers=child_headers,
            json={"family_id": family_id, "emotion": "불안", "worry": "진로가 막막해요.", "mode": "direct"},
        )
        self.assertEqual(delivery.status_code, 201, delivery.text)
        self.assertTrue(delivery.json()["should_notify"])
        self.assertEqual(len(delivery.json()["questions"]), 1)

        polished = self.client.post(
            "/api/answers/polish",
            headers=parent_headers,
            json={"question": delivery.json()["questions"][0], "answer": "나도 처음엔 막막했어.", "tone": "practical"},
        )
        self.assertEqual(polished.status_code, 200, polished.text)
        self.assertEqual(polished.json()["tone"], "practical")
        self.assertTrue(polished.json()["recommendation_reason"])

        final_answer = "오늘 할 수 있는 작은 일부터 하나씩 시작해 보렴."
        saved = self.client.post(
            f"/api/answers/deliveries/{delivery.json()['id']}",
            headers=parent_headers,
            json={
                "question": delivery.json()["questions"][0],
                "answer": "나도 처음엔 막막했어.",
                "final_answer": final_answer,
                "tone": "practical",
            },
        )
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json()["polished_answer"], final_answer)

        child_library = self.client.get(f"/api/answers?family_id={family_id}", headers=child_headers)
        parent_library = self.client.get(f"/api/answers?family_id={family_id}", headers=parent_headers)
        self.assertEqual(child_library.status_code, 200, child_library.text)
        self.assertEqual(parent_library.status_code, 200, parent_library.text)
        self.assertEqual(child_library.json()[0]["original_question"], delivery.json()["target_question"])
        self.assertEqual(parent_library.json()[0]["respondent_id"], parent["user"]["id"])


if __name__ == "__main__":
    unittest.main()
