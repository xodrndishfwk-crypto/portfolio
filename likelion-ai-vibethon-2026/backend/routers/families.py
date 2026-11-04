from datetime import datetime, timedelta
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from auth import get_current_user
from database import get_db
from models import Family, FamilyInvite, FamilyMember, User
from schemas.family import FamilyCreateRequest, FamilyDetailResponse, FamilyInviteResponse, FamilyJoinRequest

router = APIRouter(prefix="/api/families", tags=["families"])

def get_membership(family_id: int, user_id: int, db: Session) -> FamilyMember:
    membership = db.query(FamilyMember).filter(
        FamilyMember.family_id == family_id,
        FamilyMember.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="해당 가족의 구성원만 이용할 수 있습니다.")
    return membership

def serialize_family(family: Family) -> dict:
    return {
        "id": family.id,
        "name": family.name,
        "members": [
            {
                "user_id": member.user.id,
                "name": member.user.name,
                "email": member.user.email,
                "role": member.role,
            }
            for member in family.members
        ],
        "created_at": family.created_at,
    }

@router.post("", response_model=FamilyDetailResponse, status_code=status.HTTP_201_CREATED)
def create_family(body: FamilyCreateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    family = Family(name=body.name)
    db.add(family)
    db.flush()
    if body.nickname:
        current_user.name = body.nickname.strip()
    mem = FamilyMember(family_id=family.id, user_id=current_user.id, role=body.role)
    db.add(mem)
    db.commit()
    db.refresh(family)
    return serialize_family(family)

@router.post("/invites", response_model=FamilyInviteResponse)
def create_invite(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mem = db.query(FamilyMember).filter(FamilyMember.user_id == current_user.id).first()
    if not mem: raise HTTPException(status_code=400, detail="가족에 소속되어 있지 않습니다.")
    code = secrets.token_hex(4).upper()
    expires_at = datetime.utcnow() + timedelta(days=3)
    invite = FamilyInvite(family_id=mem.family_id, code=code, expires_at=expires_at)
    db.add(invite)
    db.commit()
    return {"invite_code": code, "expires_at": expires_at}

@router.get("/{family_id}", response_model=FamilyDetailResponse)
def get_family(family_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = get_membership(family_id, current_user.id, db)
    return serialize_family(membership.family)

@router.get("/{family_id}/invite", response_model=FamilyInviteResponse | None)
def get_active_invite(family_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_membership(family_id, current_user.id, db)
    invite = db.query(FamilyInvite).filter(
        FamilyInvite.family_id == family_id,
        FamilyInvite.expires_at > datetime.utcnow(),
    ).order_by(FamilyInvite.created_at.desc()).first()
    if not invite:
        return None
    return {"invite_code": invite.code, "expires_at": invite.expires_at}

@router.post("/{family_id}/invites", response_model=FamilyInviteResponse)
def create_family_invite(family_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_membership(family_id, current_user.id, db)
    active_invite = db.query(FamilyInvite).filter(
        FamilyInvite.family_id == family_id,
        FamilyInvite.expires_at > datetime.utcnow(),
    ).order_by(FamilyInvite.created_at.desc()).first()
    if active_invite:
        return {"invite_code": active_invite.code, "expires_at": active_invite.expires_at}
    code = secrets.token_hex(4).upper()
    expires_at = datetime.utcnow() + timedelta(days=3)
    invite = FamilyInvite(family_id=family_id, code=code, expires_at=expires_at)
    db.add(invite)
    db.commit()
    return {"invite_code": code, "expires_at": expires_at}

@router.post("/join", response_model=FamilyDetailResponse)
def join_family(body: FamilyJoinRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inv = db.query(FamilyInvite).filter(FamilyInvite.code == body.invite_code, FamilyInvite.expires_at > datetime.utcnow()).first()
    if not inv: raise HTTPException(status_code=404, detail="유효하지 않은 초대 코드입니다.")
    if db.query(FamilyMember).filter(FamilyMember.family_id == inv.family_id, FamilyMember.user_id == current_user.id).first():
        raise HTTPException(status_code=400, detail="이미 참여한 가족입니다.")
    if body.nickname:
        current_user.name = body.nickname.strip()
    mem = FamilyMember(family_id=inv.family_id, user_id=current_user.id, role=body.role)
    db.add(mem)
    db.commit()
    fam = db.query(Family).filter(Family.id == inv.family_id).first()
    return serialize_family(fam)
