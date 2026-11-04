from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class QuestionRequest(BaseModel):
    worry: str = Field(..., min_length=1)
    emotion: str = Field(default="지침")
    mode: Literal["stealth", "direct"] = "stealth"

class QuestionDeliveryCreate(BaseModel):
    family_id: int
    emotion: str
    worry: str = Field(..., min_length=1)
    recipient_id: int | None = None
    mode: Literal["stealth", "direct"] = "stealth"

class QuestionDeliveryResponse(BaseModel):
    id: int
    family_id: int
    sender_id: int
    recipient_id: int | None
    emotion: str
    mode: Literal["stealth", "direct"]
    status: Literal["pending", "answered"]
    should_notify: bool = False
    questions: list[str]
    target_question: str
    created_at: datetime
    class Config:
        from_attributes = True
