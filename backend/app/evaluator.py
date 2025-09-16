# backend/app/evaluator.py
import os
import pathlib
import asyncio
import json
from dotenv import load_dotenv
import openai  # ✅ use functional API
from typing import Dict, List, Any

# load backend/.env
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# Configure once
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY not set in backend/.env or Render env variables.")
openai.api_key = OPENAI_API_KEY


def keyword_score(answer: str, expected_keywords: List[str]) -> float:
    """Deterministic keyword coverage score (0.0 - 1.0)."""
    if not expected_keywords:
        return 1.0
    ans = (answer or "").lower()
    hits = sum(1 for k in expected_keywords if k.lower() in ans)
    return round(hits / len(expected_keywords), 3)


async def _call_llm_system(prompt: str, expect_json: bool = True) -> Dict[str, Any]:
    """Call OpenAI ChatCompletion and parse JSON if required."""
    try:
        resp = await asyncio.to_thread(
            openai.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=400,
        )

        text = resp.choices[0].message.content.strip()

        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        return json.loads(text) if expect_json else {"raw": text}

    except Exception as e:
        return {"score": None, "reasoning": f"LLM error: {e}", "suggestions": []}


async def plagiarism_check(answer: str) -> Dict[str, Any]:
    """Detect if answer looks AI-generated or copied."""
    if not answer.strip():
        return {"status": "empty", "explanation": "No answer provided."}

    prompt = (
        f"Analyze this text:\n\n{answer}\n\n"
        "Classify as:\n"
        "- 'original': written by a human in their own words.\n"
        "- 'suspicious': likely AI-generated or copied.\n\n"
        "Return JSON {status, explanation}"
    )

    result = await _call_llm_system(prompt, expect_json=True)
    return {
        "status": result.get("status", "unknown"),
        "explanation": result.get("explanation", "No explanation provided")
    }


async def evaluate_answer(question: Dict[str, Any], answer: str) -> Dict[str, Any]:
    """Evaluate candidate's answer with keywords + LLM + plagiarism check."""
    expected_keywords = question.get("expected_keywords", []) or []
    kw = keyword_score(answer, expected_keywords)

    prompt = (
        f"Question: {question.get('text')}\n\n"
        f"Expected: {expected_keywords}\n\n"
        f"Answer: {answer}\n\n"
        "Return JSON {score: float 0-1, reasoning: str, suggestions: [..]}"
    )

    llm_result = await _call_llm_system(prompt, expect_json=True)

    llm_score = llm_result.get("score")
    try:
        llm_score = float(llm_score) if llm_score is not None else kw
        llm_score = max(0.0, min(1.0, llm_score))
    except Exception:
        llm_score = kw

    final_score = round(0.4 * kw + 0.6 * llm_score, 3)

    plagiarism_result = await plagiarism_check(answer)

    return {
        "question_id": question.get("id"),
        "question_text": question.get("text"),
        "difficulty": question.get("difficulty", ""),
        "answer": answer,
        "score": final_score,
        "reasoning": llm_result.get("reasoning") or f"Keyword baseline: {kw}",
        "suggestions": llm_result.get("suggestions") or [],
        "plagiarism_check": plagiarism_result,
    }
