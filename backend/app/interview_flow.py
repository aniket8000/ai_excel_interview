import os
import json
import asyncio
from datetime import datetime
import uuid
from typing import Dict, List, Optional
from dotenv import load_dotenv
import openai  # ✅ use functional API

# Load backend/.env
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Configure API key once
openai.api_key = os.getenv("OPENAI_API_KEY")


async def generate_excel_questions(n: int = 5) -> List[Dict]:
    """
    Generate Excel questions with increasing difficulty.
    Each question includes: id, text, type, expected_keywords, difficulty.
    """

    prompt = (
        f"Generate {n} Excel interview questions with increasing difficulty. "
        "Start from easy and move up to expert level. "
        "Mix theory, formulas, pivot tables, scenarios, and error handling. "
        "Return strictly a JSON array of objects with fields: "
        "[{id, text, type, expected_keywords, difficulty}] "
        "where 'type' ∈ {theory, practical, scenario} and "
        "'difficulty' ∈ {easy, medium, hard, very hard, expert}."
    )

    try:
        resp = await asyncio.to_thread(
            openai.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI interviewer. Always reply in valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )

        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.strip("`").replace("json", "", 1).strip()

        return json.loads(text)

    except Exception as e:
        print("⚠️ Question generation failed, fallback used. Error:", e)
        return [
            {"id": "fallback_q1", "text": "Explain relative vs absolute references.", "type": "theory",
             "expected_keywords": ["relative", "absolute", "cell reference"], "difficulty": "easy"},
            {"id": "fallback_q2", "text": "Write a VLOOKUP to fetch employee salary.", "type": "practical",
             "expected_keywords": ["VLOOKUP", "formula", "table"], "difficulty": "medium"},
            {"id": "fallback_q3", "text": "How do you handle errors with IFERROR?", "type": "theory",
             "expected_keywords": ["IFERROR", "formula", "error"], "difficulty": "hard"},
            {"id": "fallback_q4", "text": "Describe how to create and analyze a Pivot Table.", "type": "scenario",
             "expected_keywords": ["Pivot Table", "rows", "columns"], "difficulty": "very hard"},
            {"id": "fallback_q5", "text": "Optimize a slow Excel sheet with many formulas.", "type": "scenario",
             "expected_keywords": ["optimization", "Excel performance"], "difficulty": "expert"},
        ]


class InterviewState:
    def __init__(self, candidate_name: str, total_questions: int = 5):
        self.id = str(uuid.uuid4())
        self.candidate_name = candidate_name
        self.started_at = datetime.utcnow()
        self.turns: List[Dict] = []
        self.current_q_index = 0
        self.finished = False
        self.total_questions = total_questions

        self.questions: List[Dict] = []
        self.last_question: Optional[Dict] = None
        self.question_answer_pairs: List = []
        self.evaluations: List[Dict] = []   # store evaluations as we go

    async def load_questions(self):
        self.questions = await generate_excel_questions(self.total_questions)

    def next_question(self) -> Optional[Dict]:
        if self.current_q_index >= self.total_questions:
            self.finished = True
            return None
        q = self.questions[self.current_q_index]
        self.current_q_index += 1
        self.last_question = q
        return q

    def add_turn(self, role: str, text: str):
        self.turns.append({
            "role": role,
            "text": text,
            "ts": datetime.utcnow(),
        })
        if role == "candidate" and self.last_question:
            self.question_answer_pairs.append((self.last_question, text))

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "candidate_name": self.candidate_name,
            "started_at": self.started_at,
            "turns": self.turns,
            "finished": self.finished,
            "current_q_index": self.current_q_index,
            "total_questions": self.total_questions,
        }
