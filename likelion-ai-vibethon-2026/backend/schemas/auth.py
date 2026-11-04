from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from schemas.family import FamilyDetailResponse

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=4)
    name: str = Field(..., min_length=1, max_length=50)

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    family: FamilyDetailResponse | None = None
