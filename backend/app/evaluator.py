# backend/app/evaluator.py
import os
import pathlib
import asyncio
import json
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, List, Any

# load backend/.env
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# Defensive check
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in backend/.env")


def get_openai_client():
    """Lazy load OpenAI client to avoid reload/proxy issues."""
    return OpenAI()


def keyword_score(answer: str, expected_keywords: List[str]) -> float:
    """Deterministic keyword coverage score (0.0 - 1.0)."""
    if not expected_keywords:
        return 1.0
    ans = (answer or "").lower()
    hits = sum(1 for k in expected_keywords if k.lower() in ans)
    return round(hits / len(expected_keywords), 3)


async def _call_llm_system(prompt: str, expect_json: bool = True) -> Dict[str, Any]:
    """
    Call OpenAI ChatCompletion.
    If expect_json=True, enforce JSON parsing.
    """
    client = get_openai_client()

    try:
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=400,
        )

        text = resp.choices[0].message.content.strip()

        # remove ``` fences if model added them
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        if expect_json:
            return json.loads(text)
        else:
            return {"raw": text}

    except Exception as e:
        return {"score": None, "reasoning": f"LLM error: {e}", "suggestions": []}


async def plagiarism_check(answer: str) -> Dict[str, Any]:
    """
    Detect if answer looks AI-generated or copied.
    Returns {status: "original" | "suspicious", explanation: str}.
    """
    if not answer.strip():
        return {"status": "empty", "explanation": "No answer provided."}

    prompt = (
        f"Analyze the following text:\n\n{answer}\n\n"
        "Classify if the response is:\n"
        "- 'original': written by a human in their own words.\n"
        "- 'suspicious': likely AI-generated, copied, or too generic.\n\n"
        "Return a JSON object with fields:\n"
        " - status (original or suspicious)\n"
        " - explanation (short reason)"
    )

    result = await _call_llm_system(prompt, expect_json=True)

    status = result.get("status", "unknown")
    explanation = result.get("explanation", "No explanation provided")

    return {"status": status, "explanation": explanation}


async def evaluate_answer(question: Dict[str, Any], answer: str) -> Dict[str, Any]:
    """
    Combined evaluation:
    - deterministic keyword baseline
    - LLM qualitative judgement
    - plagiarism/AI-detection check
    """
    expected_keywords = question.get("expected_keywords", []) or []
    kw = keyword_score(answer, expected_keywords)

    prompt = (
        f"Question: {question.get('text')}\n\n"
        f"Expected keywords / concepts: {expected_keywords}\n\n"
        f"Candidate answer: {answer}\n\n"
        "Provide a JSON object with fields:\n"
        " - score: a number between 0 and 1 (float)\n"
        " - reasoning: short explanation (1-2 sentences)\n"
        " - suggestions: list of 1-3 concise improvement suggestions\n\n"
        "Be objective and concise."
    )

    llm_result = await _call_llm_system(prompt, expect_json=True)

    llm_score = llm_result.get("score")
    try:
        if llm_score is None:
            llm_score = kw
        else:
            llm_score = float(llm_score)
            llm_score = max(0.0, min(1.0, llm_score))
    except Exception:
        llm_score = kw

    final_score = round(0.4 * kw + 0.6 * llm_score, 3)

    reasoning = llm_result.get("reasoning") or f"Keyword coverage baseline: {kw}"
    suggestions = llm_result.get("suggestions") or []

    # 🔍 Run plagiarism check
    plagiarism_result = await plagiarism_check(answer)

    return {
        "question_id": question.get("id"),
        "question_text": question.get("text"),        # ✅ store full question
        "difficulty": question.get("difficulty", ""), # ✅ store difficulty (easy/medium/hard)
        "answer": answer,                             # ✅ store user answer
        "score": final_score,
        "reasoning": reasoning if isinstance(reasoning, str) else str(reasoning),
        "suggestions": suggestions,
        "plagiarism_check": plagiarism_result,        # ✅ store plagiarism
    }
