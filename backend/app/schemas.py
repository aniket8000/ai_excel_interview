from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class Question(BaseModel):
    id: str
    text: str
    type: str
    expected_keywords: Optional[List[str]] = []

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
    finished_at: Optional[datetime]

class Evaluation(BaseModel):
    question_id: str
    score: float
    reasoning: str
    suggestions: Optional[List[str]] = []

class Report(BaseModel):
    transcript_id: str
    candidate_name: str
    evaluations: List[Evaluation]
    overall_score: float
    strengths: List[str]
    weaknesses: List[str]
    generated_at: datetime
