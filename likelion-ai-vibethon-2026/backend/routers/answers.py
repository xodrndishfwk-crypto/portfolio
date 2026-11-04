import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from auth import get_current_user
from database import get_db
from models import Answer, FamilyMember, QuestionDelivery, Reaction, User
from schemas.answer import AnswerCreateRequest, AnswerRequest, AnswerResponse, ReactionRequest
from services.answer_service import polish_answer

router = APIRouter(prefix="/api/answers", tags=["answers"])

CHILD_ROLES = ("son", "daughter", "child")
PARENT_ROLES = ("father", "mother", "parent")

@router.post("/polish")
def polish(body: AnswerRequest):
    return polish_answer(body)

@router.post("/deliveries/{delivery_id}", response_model=AnswerResponse, status_code=status.HTTP_201_CREATED)
def submit_answer(delivery_id: int, body: AnswerCreateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delivery = db.query(QuestionDelivery).filter(QuestionDelivery.id == delivery_id).first()
    if not delivery: raise HTTPException(status_code=404, detail="질문이 없습니다.")
    mem = db.query(FamilyMember).filter(FamilyMember.family_id == delivery.family_id, FamilyMember.user_id == current_user.id).first()
    if not mem or mem.role not in PARENT_ROLES:
        raise HTTPException(status_code=403, detail="부모 권한만 답변 가능합니다.")
    if delivery.recipient_id is not None and delivery.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="이 질문의 수신자로 지정된 부모만 답변할 수 있습니다.")
    bundle = [delivery.target_question]
    if delivery.questions_bundle:
        try:
            parsed = json.loads(delivery.questions_bundle)
            if isinstance(parsed, list):
                bundle = parsed
        except Exception:
            bundle = [delivery.target_question]
    if body.question != delivery.target_question and body.question not in bundle:
        raise HTTPException(status_code=400, detail="전달된 질문 중 하나를 선택해 주세요.")

    final_answer = body.final_answer
    if not final_answer:
        final_answer = polish_answer(AnswerRequest(answer=body.answer, question=body.question, tone=body.tone))["polished"]
    answer = Answer(
        delivery_id=delivery.id,
        respondent_id=current_user.id,
        question=body.question,
        raw_answer=body.answer,
        polished_answer=final_answer,
    )
    db.add(answer)
    delivery.status = "answered"
    db.commit()
    db.refresh(answer)
    return {
        "id": answer.id,
        "delivery_id": answer.delivery_id,
        "respondent_id": answer.respondent_id,
        "author_name": current_user.name,
        "emotion": delivery.emotion,
        "original_question": delivery.target_question,
        "question": answer.question,
        "raw_answer": answer.raw_answer,
        "polished_answer": answer.polished_answer,
        "thanks_count": 0,
        "moved_count": 0,
        "reference_answers": [],
        "created_at": answer.created_at,
    }

@router.get("", response_model=list[AnswerResponse])
def get_library_answers(family_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = db.query(FamilyMember).filter(
        FamilyMember.family_id == family_id,
        FamilyMember.user_id == current_user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="조회 권한이 없습니다.")
    query = db.query(Answer).join(QuestionDelivery, Answer.delivery_id == QuestionDelivery.id).filter(QuestionDelivery.family_id == family_id)
    if membership.role in CHILD_ROLES:
        query = query.filter(QuestionDelivery.sender_id == current_user.id)
    else:
        query = query.filter(Answer.respondent_id == current_user.id)
    answers = query.order_by(Answer.created_at.desc()).all()
    res = []
    for a in answers:
        u = db.query(User).filter(User.id == a.respondent_id).first()
        tc = db.query(Reaction).filter(Reaction.answer_id == a.id, Reaction.reaction_type == "thanks").count()
        mc = db.query(Reaction).filter(Reaction.answer_id == a.id, Reaction.reaction_type == "moved").count()
        references = []
        if membership.role in CHILD_ROLES and a.delivery:
            related = db.query(Answer).join(QuestionDelivery, Answer.delivery_id == QuestionDelivery.id).filter(
                QuestionDelivery.family_id != family_id,
                QuestionDelivery.target_question == a.delivery.target_question,
                Answer.question == a.delivery.target_question,
            ).order_by(Answer.created_at.desc()).limit(5).all()
            references = [
                {"polished_answer": item.polished_answer, "created_at": item.created_at}
                for item in related
            ]
        res.append({
            "id": a.id,
            "delivery_id": a.delivery_id,
            "respondent_id": a.respondent_id,
            "author_name": u.name if u else "부모님",
            "emotion": a.delivery.emotion if a.delivery else None,
            "original_question": a.delivery.target_question if a.delivery else a.question,
            "question": a.question,
            "raw_answer": a.raw_answer,
            "polished_answer": a.polished_answer,
            "thanks_count": tc,
            "moved_count": mc,
            "reference_answers": references,
            "created_at": a.created_at,
        })
    return res

@router.post("/{answer_id}/reactions")
def react_answer(answer_id: int, body: ReactionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    answer = db.query(Answer).filter(Answer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="답변을 찾을 수 없습니다.")
    membership = db.query(FamilyMember).filter(
        FamilyMember.family_id == answer.delivery.family_id,
        FamilyMember.user_id == current_user.id,
    ).first()
    can_access = membership and (
        (membership.role in CHILD_ROLES and answer.delivery.sender_id == current_user.id)
        or (membership.role in PARENT_ROLES and answer.respondent_id == current_user.id)
    )
    if not can_access:
        raise HTTPException(status_code=403, detail="내 서재의 답변에만 반응할 수 있습니다.")
    reaction = Reaction(answer_id=answer_id, user_id=current_user.id, reaction_type=body.reaction_type)
    db.add(reaction)
    db.commit()
    return {"message": "반응 완료"}
