# backend/app/main.py
import os
import pathlib
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from dotenv import load_dotenv

# local modules
from .interview_flow import InterviewState
from .evaluator import evaluate_answer
from .db import transcripts_collection, reports_collection
from .utils import create_report_from_evaluations

# load backend/.env
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

app = FastAPI(title="AI Excel Mock Interviewer", version="1.0")

# allow frontend + admin panel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# in-memory session store
interviews: Dict[str, InterviewState] = {}


# ✅ helper to fix Mongo ObjectId + datetime in responses
def fix_mongo_ids(doc):
    if isinstance(doc, list):
        return [fix_mongo_ids(x) for x in doc]
    if isinstance(doc, dict):
        return {k: fix_mongo_ids(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ------------------------------
# 🎤 Interview Flow Endpoints
# ------------------------------

@app.post("/start")
async def start_interview(payload: Dict[str, Any]):
    candidate_name = payload.get("candidate_name")
    if not candidate_name:
        raise HTTPException(status_code=400, detail="candidate_name required")

    state = InterviewState(candidate_name=candidate_name)
    await state.load_questions()
    interviews[state.id] = state

    intro = (
        f"Hello {candidate_name}! I'm the AI Excel Mock Interviewer. "
        "I'll ask a few questions about Excel (theory, formulas, and scenarios). "
        "Answer as you would in a live interview. Let's begin."
    )
    state.add_turn("interviewer", intro)

    q = state.next_question()
    if q:
        state.add_turn("interviewer", q["text"])
        return {
            "id": state.id,
            "question": q["text"],
            "intro": intro,
            "progress": f"1/{state.total_questions}"
        }
    else:
        state.finished = True
        return {"id": state.id, "message": "No questions configured."}


@app.post("/answer/{interview_id}")
async def answer_question(interview_id: str, payload: Dict[str, Any]):
    state = interviews.get(interview_id)
    if not state:
        raise HTTPException(status_code=404, detail="Interview not found")
    if state.finished:
        raise HTTPException(status_code=400, detail="Interview already finished")

    answer = payload.get("answer", "") or ""
    state.add_turn("candidate", answer)

    last_q = state.last_question
    if not last_q:
        eval_result = {
            "question_id": "unknown",
            "score": 0.0,
            "reasoning": "No question context",
            "suggestions": [],
        }
    else:
        eval_result = await evaluate_answer(last_q, answer)
        eval_result["question_text"] = last_q.get("text")
        eval_result["difficulty"] = last_q.get("difficulty", "unknown")
        eval_result["answer"] = answer

    if not hasattr(state, "evaluations"):
        state.evaluations = []
    state.evaluations.append(eval_result)

    if state.current_q_index < state.total_questions:
        next_q = state.next_question()
        if next_q:
            state.add_turn("interviewer", next_q["text"])
            return {
                "evaluation": eval_result,
                "next_question": next_q["text"],
                "progress": f"{state.current_q_index}/{state.total_questions}",
            }

    state.finished = True
    closing = "Thanks — the interview is complete. We'll generate a short performance summary."
    state.add_turn("interviewer", closing)

    transcript = state.to_dict()
    transcript["finished_at"] = datetime.utcnow()

    try:
        result = await transcripts_collection.insert_one(transcript)
        transcript["_id"] = str(result.inserted_id)
    except Exception as e:
        print("DB insert transcript failed:", e)

    evaluations = getattr(state, "evaluations", [])

    report_doc = create_report_from_evaluations(
        transcript["id"], transcript["candidate_name"], evaluations
    )

    try:
        result = await reports_collection.insert_one(report_doc)
        report_doc["_id"] = str(result.inserted_id)
    except Exception as e:
        print("DB insert report failed:", e)

    return fix_mongo_ids({
        "evaluation": eval_result,
        "message": closing,
        "report": report_doc
    })


# ------------------------------
# 📊 Admin Endpoints
# ------------------------------

@app.get("/reports")
@app.get("/admin/reports")
async def list_reports(
    from_date: Optional[str] = Query(None, description="Filter reports created after this date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter reports created before this date (YYYY-MM-DD)"),
):
    """List all interview reports, optionally filtered by date range."""
    query = {}

    if from_date or to_date:
        date_filter = {}
        if from_date:
            date_filter["$gte"] = datetime.fromisoformat(from_date)
        if to_date:
            to_dt = datetime.fromisoformat(to_date) + timedelta(days=1)
            date_filter["$lt"] = to_dt
        query["generated_at"] = date_filter

    docs = await reports_collection.find(query).to_list(length=1000)
    return fix_mongo_ids(docs)


@app.get("/admin/report/{report_id}")
async def get_report(report_id: str):
    """Get one report by ID."""
    doc = await reports_collection.find_one({"_id": ObjectId(report_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    return fix_mongo_ids(doc)


@app.get("/admin/analytics")
async def analytics():
    """Basic stats for dashboard."""
    docs = await reports_collection.find().to_list(length=1000)
    if not docs:
        return {"count": 0, "avg_score": 0, "difficulty_distribution": {}, "plagiarism": {}}

    total = len(docs)
    avg_score = sum(d.get("overall_score", 0) for d in docs) / total

    difficulty_counts = {}
    plagiarism_counts = {"original": 0, "suspicious": 0, "empty": 0}

    for d in docs:
        for ev in d.get("evaluations", []):
            diff = ev.get("difficulty", "unknown")
            difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1

            pc = ev.get("plagiarism_check", {})
            status = pc.get("status", "unknown")
            plagiarism_counts[status] = plagiarism_counts.get(status, 0) + 1

    return {
        "count": total,
        "avg_score": round(avg_score, 3),
        "difficulty_distribution": difficulty_counts,
        "plagiarism": plagiarism_counts,
    }
