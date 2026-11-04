import os
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models import Base


class QuestionPoolTest(unittest.TestCase):
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
        self.client.post("/api/auth/register", json={"email": email, "password": "pass", "name": name})
        res = self.client.post("/api/auth/login", json={"email": email, "password": "pass"})
        return res.json()

    def auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_question_pool_dynamic_flow(self):
        child = self.register_and_login("c_pool@test.com", "자녀")
        parent = self.register_and_login("p_pool@test.com", "부모")
        child_hdr = self.auth(child["access_token"])
        parent_hdr = self.auth(parent["access_token"])

        fam = self.client.post("/api/families", headers=child_hdr, json={"name": "화목한 가족", "role": "child"}).json()
        invite = self.client.post(f"/api/families/{fam['id']}/invites", headers=child_hdr).json()
        self.client.post("/api/families/join", headers=parent_hdr, json={"invite_code": invite["invite_code"], "role": "parent"})

        # 1. 자식이 아무 질문을 하지 않았더라도 부모에게 10개의 기본 질문이 제공되어야 함 (10/0)
        res = self.client.get(f"/api/questions/deliveries?family_id={fam['id']}&status=pending", headers=parent_hdr)
        self.assertEqual(res.status_code, 200)
        pool = res.json()
        self.assertEqual(len(pool), 10, "자녀가 질문하지 않아도 기본 질문 10개가 제공되어야 함")

        initial_questions = [item["questions"][0] for item in pool]
        self.assertEqual(len(set(initial_questions)), 10, "초기 10개 질문은 모두 고유해야 함")

        # 2. 자녀가 위장 질문 1개(C1) 등록 -> 9/1 상태
        send1 = self.client.post(
            "/api/questions/deliveries",
            headers=child_hdr,
            json={"family_id": fam["id"], "emotion": "지침", "worry": "취업이 너무 어렵고 지쳐요.", "mode": "stealth"},
        )
        self.assertEqual(send1.status_code, 201)
        c1_target = send1.json()["target_question"]

        res2 = self.client.get(f"/api/questions/deliveries?family_id={fam['id']}&status=pending", headers=parent_hdr)
        pool2 = res2.json()
        self.assertEqual(len(pool2), 10, "질문 풀은 여전히 10개 유지")
        pool2_questions = [item["questions"][0] for item in pool2]
        self.assertIn(c1_target, pool2_questions, "자녀의 위장 질문 C1이 10개 풀에 포함되어야 함")

        # 3. 부모가 초기 보편 질문 중 1개(Q1)에 답변 작성 -> Q1 영구 소모
        general_q1_item = next(item for item in pool2 if item["questions"][0] != c1_target)
        q1_text = general_q1_item["questions"][0]
        q1_id = general_q1_item["id"]

        ans1 = self.client.post(
            f"/api/answers/deliveries/{q1_id}",
            headers=parent_hdr,
            json={"question": q1_text, "answer": "나도 젊었을 때 참 힘들었지만 묵묵히 버텼단다."},
        )
        self.assertEqual(ans1.status_code, 201)

        # 4. 그 사이에 자녀가 위장 질문 1개(C2)를 더 등록함
        send2 = self.client.post(
            "/api/questions/deliveries",
            headers=child_hdr,
            json={"family_id": fam["id"], "emotion": "불안", "worry": "인간관계 때문에 마음이 너무 힘들어요.", "mode": "stealth"},
        )
        self.assertEqual(send2.status_code, 201)
        c2_target = send2.json()["target_question"]

        # 이제 풀을 조회하면: 보편 8개 + 자녀 2개 (8/2) = 총 10개!
        res3 = self.client.get(f"/api/questions/deliveries?family_id={fam['id']}&status=pending", headers=parent_hdr)
        pool3 = res3.json()
        self.assertEqual(len(pool3), 10, "총 10개 풀 유지")
        pool3_questions = [item["questions"][0] for item in pool3]

        # 영구 소모 검증: 답변했던 q1_text는 다시 나타나지 않아야 함
        self.assertNotIn(q1_text, pool3_questions, "답변을 완료한 질문은 영원히 다시 나타나지 않아야 함")

        # 자녀 위장 질문 2개(C1, C2)가 모두 풀에 들어있어야 함 (8/2 구성)
        self.assertIn(c1_target, pool3_questions, "자녀 질문 C1 포함")
        self.assertIn(c2_target, pool3_questions, "자녀 질문 C2 포함")

        # 5. 부모가 자녀 위장 질문 C1에 답변을 작성
        c1_item = next(item for item in pool3 if item["questions"][0] == c1_target)
        ans2 = self.client.post(
            f"/api/answers/deliveries/{c1_item['id']}",
            headers=parent_hdr,
            json={"question": c1_target, "answer": "조급해하지 않아도 돼. 천천히 걸어가도 괜찮단다."},
        )
        self.assertEqual(ans2.status_code, 201)

        # 이제 풀을 조회하면: C1은 소모되었고 C2는 남아있으며 새 보편 질문이 채워져 여전히 10개 (보편 9 + 자녀 1)
        res4 = self.client.get(f"/api/questions/deliveries?family_id={fam['id']}&status=pending", headers=parent_hdr)
        pool4 = res4.json()
        self.assertEqual(len(pool4), 10, "여전히 10개 유지")
        pool4_questions = [item["questions"][0] for item in pool4]
        self.assertNotIn(c1_target, pool4_questions, "답변된 자녀 질문 C1은 풀에서 제거됨")
        self.assertIn(c2_target, pool4_questions, "아직 미답변된 자녀 질문 C2는 남아있음")


if __name__ == "__main__":
    unittest.main()
