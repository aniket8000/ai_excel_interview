# backend/app/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Question(BaseModel):
    id: str
    text: str
    type: str
    expected_keywords: List[str] = Field(default_factory=list)

class Turn(BaseModel):
    role: str  # "interviewer" | "candidate"
    text: str
    ts: datetime

class TranscriptIn(BaseModel):
    candidate_name: str

class TranscriptDB(BaseModel):
    id: str
    candidate_name: str
    turns: List[Turn]
    started_at: datetime
    finished_at: Optional[datetime] = None

class Evaluation(BaseModel):
    question_id: str
    score: float
    reasoning: str
    suggestions: List[str] = Field(default_factory=list)

class Report(BaseModel):
    transcript_id: str
    candidate_name: str
    evaluations: List[Evaluation]
    overall_score: float
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    generated_at: datetime
