from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from auth import create_access_token, get_password_hash, verify_password
from database import get_db
from models import FamilyMember, User
from schemas.auth import TokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: UserRegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 등록된 이메일입니다.")
    user = User(email=body.email, password_hash=get_password_hash(body.password), name=body.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=TokenResponse)
def login(body: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 잘못되었습니다.")
    token = create_access_token({"sub": user.email, "uid": user.id})
    membership = (
        db.query(FamilyMember)
        .filter(FamilyMember.user_id == user.id)
        .order_by(FamilyMember.id.desc())
        .first()
    )
    family_data = None
    if membership:
        family = membership.family
        family_data = {
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
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
        "family": family_data,
    }
