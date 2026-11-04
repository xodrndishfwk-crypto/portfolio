from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    tone: Literal["firm", "warm", "calm", "practical", "friendly"] = "warm"

class AnswerCreateRequest(BaseModel):
    question: str
    answer: str = Field(..., min_length=1)
    final_answer: str | None = Field(default=None, min_length=1)
    tone: Literal["firm", "warm", "calm", "practical", "friendly"] = "warm"

class ReferenceAnswerResponse(BaseModel):
    polished_answer: str
    created_at: datetime

class AnswerResponse(BaseModel):
    id: int
    delivery_id: int
    respondent_id: int
    author_name: str | None = None
    emotion: str | None = None
    original_question: str | None = None
    question: str
    raw_answer: str
    polished_answer: str
    thanks_count: int = 0
    moved_count: int = 0
    reference_answers: list[ReferenceAnswerResponse] = Field(default_factory=list)
    created_at: datetime
    class Config:
        from_attributes = True

class ReactionRequest(BaseModel):
    reaction_type: Literal["thanks", "moved"]
