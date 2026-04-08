from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    subscription_tier: str

    class Config:
        from_attributes = True


class AnalysisResponse(BaseModel):
    risky_clauses: List[str]
    suggestions: List[str]
    summary: str
    confidence_score: float


class KnowledgeBaseCreate(BaseModel):
    category: str
    title: str
    content: str
    tags: str = ""


class KnowledgeBaseOut(BaseModel):
    id: int
    category: str
    title: str
    content: str
    tags: str
    created_at: datetime

    class Config:
        from_attributes = True


class LearningOutcomeCreate(BaseModel):
    document_id: int
    outcome: str
    notes: str


class BillingSummary(BaseModel):
    subscription_tier: str
    total_cost_usd: float
    total_uploads: int
    total_analyses: int
