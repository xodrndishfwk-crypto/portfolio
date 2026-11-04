import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from auth import get_current_user
from database import get_db
from models import FamilyMember, QuestionDelivery, User
from schemas.question import QuestionDeliveryCreate, QuestionDeliveryResponse, QuestionRequest
from services.question_service import ensure_family_question_pool, transform_question

router = APIRouter(prefix="/api/questions", tags=["questions"])

CHILD_ROLES = ("son", "daughter", "child")
PARENT_ROLES = ("father", "mother", "parent")

def serialize_delivery(delivery: QuestionDelivery) -> dict:
    # 단일 질문 피드 형태를 위해 target_question을 기본 questions로 제공
    questions = [delivery.target_question]
    if delivery.mode == "direct":
        questions = [delivery.target_question]
    elif delivery.questions_bundle:
        try:
            bundle = json.loads(delivery.questions_bundle)
            if isinstance(bundle, list) and len(bundle) > 0:
                questions = bundle
        except Exception:
            questions = [delivery.target_question]

    should_notify = delivery.mode == "direct" or delivery.created_at <= datetime.utcnow() - timedelta(hours=24)
    # 시스템 보편 질문은 부모에게 'stealth'(자연스러운 문답)로 위장 전달
    client_mode = "stealth" if delivery.mode in ("stealth", "system") else delivery.mode

    return {
        "id": delivery.id,
        "family_id": delivery.family_id,
        "sender_id": delivery.sender_id,
        "recipient_id": delivery.recipient_id,
        "emotion": delivery.emotion,
        "mode": client_mode,
        "status": delivery.status,
        "should_notify": should_notify and delivery.status == "pending",
        "questions": questions,
        "target_question": delivery.target_question,
        "created_at": delivery.created_at,
    }

@router.post("/transform")
def transform(body: QuestionRequest):
    return transform_question(body)

@router.post("/deliveries", response_model=QuestionDeliveryResponse, status_code=status.HTTP_201_CREATED)
def create_question_delivery(body: QuestionDeliveryCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mem = db.query(FamilyMember).filter(FamilyMember.family_id == body.family_id, FamilyMember.user_id == current_user.id).first()
    if not mem or mem.role not in CHILD_ROLES:
        raise HTTPException(status_code=403, detail="자녀 권한만 마음을 보낼 수 있습니다.")
    if body.recipient_id is not None:
        recipient = db.query(FamilyMember).filter(
            FamilyMember.family_id == body.family_id,
            FamilyMember.user_id == body.recipient_id,
            FamilyMember.role.in_(PARENT_ROLES),
        ).first()
        if not recipient:
            raise HTTPException(status_code=400, detail="수신자는 해당 가족의 부모 구성원이어야 합니다.")
    req = QuestionRequest(worry=body.worry, emotion=body.emotion, mode=body.mode)
    res = transform_question(req)
    # 위장 질문(stealth)일 때도 질문 풀(10개 풀)의 1개 슬롯으로 들어가므로 target_question을 담아 생성
    delivery_questions = [res["target_question"]] if body.mode == "stealth" else res["questions"]
    delivery = QuestionDelivery(
        family_id=body.family_id, sender_id=current_user.id, recipient_id=body.recipient_id,
        emotion=body.emotion, mode=body.mode, target_question=res["target_question"],
        questions_bundle=json.dumps(delivery_questions, ensure_ascii=False), status="pending"
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return serialize_delivery(delivery)

@router.get("/deliveries", response_model=list[QuestionDeliveryResponse])
def get_question_deliveries(family_id: int, status: str = Query("pending"), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mem = db.query(FamilyMember).filter(FamilyMember.family_id == family_id, FamilyMember.user_id == current_user.id).first()
    if not mem: raise HTTPException(status_code=403, detail="조회 권한이 없습니다.")
    if status not in {"pending", "answered", "all"}:
        raise HTTPException(status_code=400, detail="status는 pending, answered 또는 all이어야 합니다.")

    if mem.role in PARENT_ROLES and status == "pending":
        # 부모가 미답변 질문을 조회할 때는 항상 기본 10개 질문 풀을 유지하여 반환 (위장 질문 + 보편 질문 동적 조합)
        deliveries = ensure_family_question_pool(db, family_id, current_user.id)
        return [serialize_delivery(delivery) for delivery in deliveries]

    query = db.query(QuestionDelivery).filter(QuestionDelivery.family_id == family_id)
    if mem.role in PARENT_ROLES:
        query = query.filter((QuestionDelivery.recipient_id == current_user.id) | (QuestionDelivery.recipient_id.is_(None)))
    else:
        # 자녀는 자신이 보낸 배달만 확인 (시스템 보편 질문 제외)
        query = query.filter(QuestionDelivery.sender_id == current_user.id)

    if status != "all":
        query = query.filter(QuestionDelivery.status == status)
    deliveries = query.order_by(QuestionDelivery.created_at.desc()).all()
    return [serialize_delivery(delivery) for delivery in deliveries]

