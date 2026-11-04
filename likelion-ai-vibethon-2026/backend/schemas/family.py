from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class FamilyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    role: Literal["son", "daughter", "father", "mother", "parent", "child"]
    nickname: str | None = Field(default=None, min_length=1, max_length=12)

class FamilyJoinRequest(BaseModel):
    invite_code: str = Field(..., min_length=6, max_length=32)
    role: Literal["son", "daughter", "father", "mother", "parent", "child"]
    nickname: str | None = Field(default=None, min_length=1, max_length=12)

class FamilyInviteResponse(BaseModel):
    invite_code: str
    expires_at: datetime

class FamilyMemberResponse(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    class Config:
        from_attributes = True

class FamilyDetailResponse(BaseModel):
    id: int
    name: str
    members: list[FamilyMemberResponse] = []
    created_at: datetime
    class Config:
        from_attributes = True
