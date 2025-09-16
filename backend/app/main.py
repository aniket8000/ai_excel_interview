# backend/app/main.py
import os
import pathlib
import logging
from fastapi import FastAPI, HTTPException, Query, Request
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

# ------ logging ------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-exam-backend")

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


# helper to fix Mongo ObjectId + datetime in responses
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


@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI Excel Mock Interviewer backend.")
    # optional: simple check that DB collections are available (non-blocking best-effort)
    try:
        # try a quick count (will raise if DB unreachable)
        await transcripts_collection.find_one({}, projection={"_id": 1})
        logger.info("Mongo collections appear accessible.")
    except Exception as e:
        logger.warning("DB startup check failed (may still be okay): %s", e)


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ------------------------------
# 🎤 Interview Flow Endpoints
# ------------------------------

@app.post("/start")
async def start_interview(payload: Dict[str, Any]):
    candidate_name = (payload or {}).get("candidate_name")
    if not candidate_name or not isinstance(candidate_name, str):
        raise HTTPException(status_code=400, detail="candidate_name (string) is required")

    logger.info("Start interview requested for candidate: %s", candidate_name)
    try:
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
    except Exception as e:
        logger.exception("Failed to start interview")
        raise HTTPException(status_code=500, detail=f"Failed to start interview: {e}")


@app.post("/answer/{interview_id}")
async def answer_question(interview_id: str, request: Request):
    """
    Expects JSON payload like:
    {
      "answer": "candidate's text answer"
    }
    """
    # get interview state
    state = interviews.get(interview_id)
    if not state:
        raise HTTPException(status_code=404, detail="Interview not found")

    if state.finished:
        raise HTTPException(status_code=400, detail="Interview already finished")

    # parse json body safely
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # validate payload has 'answer' key (string)
    answer = payload.get("answer") if isinstance(payload, dict) else None
    if answer is None or not isinstance(answer, str):
        raise HTTPException(status_code=400, detail="Payload must include 'answer' (string)")

    logger.info("Received answer for interview_id=%s; len(answer)=%d", interview_id, len(answer))

    # store turn
    state.add_turn("candidate", answer)

    # Prepare evaluation
    last_q = state.last_question
    try:
        if not last_q:
            eval_result = {
                "question_id": "unknown",
                "score": 0.0,
                "reasoning": "No question context",
                "suggestions": [],
            }
        else:
            # Run evaluation -- may call LLM and take time. Wrap in try/except.
            try:
                eval_result = await evaluate_answer(last_q, answer)
            except Exception as e:
                # LLM or evaluation failure
                logger.exception("LLM evaluation failed for interview %s", interview_id)
                eval_result = {
                    "question_id": last_q.get("id"),
                    "score": None,
                    "reasoning": f"LLM evaluation failed: {e}",
                    "suggestions": [],
                    "answer": answer,
                    "difficulty": last_q.get("difficulty", "unknown"),
                }

            # ensure some fields exist for storage
            eval_result["question_text"] = last_q.get("text")
            eval_result["difficulty"] = last_q.get("difficulty", "unknown")
            eval_result["answer"] = answer

        # append to state evaluations
        if not hasattr(state, "evaluations"):
            state.evaluations = []
        state.evaluations.append(eval_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during evaluation for interview %s", interview_id)
        raise HTTPException(status_code=500, detail=f"Evaluation error: {e}")

    # If there are more questions, return next one
    if state.current_q_index < state.total_questions:
        next_q = state.next_question()
        if next_q:
            state.add_turn("interviewer", next_q["text"])
            return {
                "evaluation": eval_result,
                "next_question": next_q["text"],
                "progress": f"{state.current_q_index}/{state.total_questions}",
            }

    # finish interview
    state.finished = True
    closing = "Thanks — the interview is complete. We'll generate a short performance summary."
    state.add_turn("interviewer", closing)

    transcript = state.to_dict()
    transcript["finished_at"] = datetime.utcnow()

    # persist transcript (best-effort). Return success even if DB insert fails, but log it.
    try:
        result = await transcripts_collection.insert_one(transcript)
        transcript["_id"] = str(result.inserted_id)
        logger.info("Inserted transcript id=%s", transcript["_id"])
    except Exception as e:
        logger.exception("DB insert transcript failed")
        # don't abort; continue to generate report in-memory

    evaluations = getattr(state, "evaluations", [])

    try:
        report_doc = create_report_from_evaluations(
            transcript["id"], transcript["candidate_name"], evaluations
        )
    except Exception:
        logger.exception("Report creation failed")
        report_doc = {
            "transcript_id": transcript.get("id"),
            "candidate_name": transcript.get("candidate_name"),
            "evaluations": evaluations,
            "overall_score": None,
            "strengths": [],
            "weaknesses": [],
            "recommendation": "Report creation failed",
            "generated_at": datetime.utcnow().isoformat(),
        }

    # persist report (best-effort)
    try:
        result = await reports_collection.insert_one(report_doc)
        report_doc["_id"] = str(result.inserted_id)
        logger.info("Inserted report id=%s", report_doc["_id"])
    except Exception as e:
        logger.exception("DB insert report failed")

    response = fix_mongo_ids({
        "evaluation": eval_result,
        "message": closing,
        "report": report_doc
    })

    return response


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
            try:
                date_filter["$gte"] = datetime.fromisoformat(from_date)
            except Exception:
                raise HTTPException(status_code=400, detail="from_date must be YYYY-MM-DD")
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date) + timedelta(days=1)
                date_filter["$lt"] = to_dt
            except Exception:
                raise HTTPException(status_code=400, detail="to_date must be YYYY-MM-DD")
        query["generated_at"] = date_filter

    try:
        docs = await reports_collection.find(query).to_list(length=1000)
        return fix_mongo_ids(docs)
    except Exception as e:
        logger.exception("Failed to list reports")
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {e}")


@app.get("/admin/report/{report_id}")
async def get_report(report_id: str):
    """Get one report by ID."""
    try:
        doc = await reports_collection.find_one({"_id": ObjectId(report_id)})
    except Exception as e:
        logger.exception("Failed to get report %s", report_id)
        raise HTTPException(status_code=500, detail=f"Failed to fetch report: {e}")

    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    return fix_mongo_ids(doc)


@app.get("/admin/analytics")
async def analytics():
    """Basic stats for dashboard."""
    try:
        docs = await reports_collection.find().to_list(length=1000)
    except Exception as e:
        logger.exception("Failed to read reports for analytics")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {e}")

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
