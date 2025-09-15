from datetime import datetime
from typing import List, Dict
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors


def create_report_from_evaluations(transcript_id: str, candidate_name: str, evaluations: List[Dict]) -> Dict:
    overall = 0.0
    strengths, weaknesses = [], []

    if evaluations:
        overall = round(sum(e.get("score", 0) for e in evaluations) / len(evaluations), 3)

    # ===== Difficulty & plagiarism analytics =====
    difficulty_stats = {"easy": [], "medium": [], "hard": []}
    plagiarism_stats = {"original": 0, "suspicious": 0, "empty": 0, "unknown": 0}

    for e in evaluations:
        # Strengths/Weaknesses
        if e.get("score", 0) >= 0.7:
            strengths.append(f"{e.get('question_id')}: {e.get('reasoning')[:80]}")
        if e.get("score", 0) <= 0.4:
            weaknesses.append(f"{e.get('question_id')}: {e.get('reasoning')[:80]}")

        # Difficulty buckets
        diff = e.get("difficulty", "").lower()
        if diff in difficulty_stats:
            difficulty_stats[diff].append(e.get("score", 0))

        # Plagiarism buckets
        pc = e.get("plagiarism_check", {})
        status = pc.get("status", "unknown").lower()
        if status in plagiarism_stats:
            plagiarism_stats[status] += 1
        else:
            plagiarism_stats["unknown"] += 1

    # Convert difficulty lists → averages
    difficulty_summary = {}
    for level, scores in difficulty_stats.items():
        if scores:
            difficulty_summary[level] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 3),
            }
        else:
            difficulty_summary[level] = {"count": 0, "avg_score": None}

    recommendation = (
        "✅ Strong Candidate — Good Excel Proficiency"
        if overall >= 0.7
        else "⚠️ Needs Improvement — Consider more practice"
    )

    return {
        "transcript_id": transcript_id,
        "candidate_name": candidate_name,
        "evaluations": evaluations,
        "overall_score": overall,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendation": recommendation,
        "generated_at": datetime.utcnow().isoformat(),
        "total_questions": len(evaluations),
        "difficulty_summary": difficulty_summary,
        "plagiarism_summary": plagiarism_stats,
    }


def generate_pdf_report(report_doc: Dict) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CenterHeading", alignment=1, fontSize=16, spaceAfter=12, leading=20))
    styles.add(ParagraphStyle(name="NormalSmall", fontSize=10, leading=14))

    elements = []

    # ===== COVER PAGE =====
    elements.append(Paragraph("AI Excel Interview Report", styles["Title"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"<b>Candidate:</b> {report_doc.get('candidate_name')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Transcript ID:</b> {report_doc.get('transcript_id')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Generated At:</b> {report_doc.get('generated_at')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Total Questions:</b> {report_doc.get('total_questions')}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"<b>Overall Score:</b> {report_doc.get('overall_score')}", styles["Heading2"]))
    elements.append(Paragraph(f"<b>Recommendation:</b> {report_doc.get('recommendation')}", styles["Heading3"]))
    elements.append(Spacer(1, 40))

    elements.append(Paragraph("Confidential — Internal Use Only", styles["NormalSmall"]))
    elements.append(PageBreak())

    # ===== DETAILED EVALUATIONS =====
    elements.append(Paragraph("Detailed Question Evaluations", styles["Heading1"]))
    elements.append(Spacer(1, 20))

    for idx, e in enumerate(report_doc.get("evaluations", []), 1):
        elements.append(Paragraph(f"<b>Q{idx}: {e.get('question_id')} [{e.get('difficulty', '').title()}]</b>", styles["Normal"]))

        if "question_text" in e:
            elements.append(Paragraph(f"<b>Question:</b> {e['question_text']}", styles["NormalSmall"]))

        if "answer" in e:
            elements.append(Paragraph(f"<b>Answer:</b> {e['answer']}", styles["NormalSmall"]))

        reasoning = e.get("reasoning", "")
        elements.append(Paragraph(f"<b>Score:</b> {e.get('score')} | <b>Reasoning:</b> {reasoning}", styles["NormalSmall"]))

        if "plagiarism_check" in e:
            pc = e["plagiarism_check"]
            explanation = pc.get("explanation", "")
            elements.append(Paragraph(f"<b>Plagiarism:</b> {pc.get('status')} ({explanation})", styles["NormalSmall"]))

        elements.append(Spacer(1, 15))

    elements.append(PageBreak())

    # ===== FINAL SUMMARY =====
    elements.append(Paragraph("Final Summary", styles["Heading1"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"<b>Overall Score:</b> {report_doc.get('overall_score')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Recommendation:</b> {report_doc.get('recommendation')}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Strengths
    elements.append(Paragraph("<b>Strengths:</b>", styles["Heading3"]))
    for s in report_doc.get("strengths", []):
        elements.append(Paragraph(f"- {s}", styles["NormalSmall"]))
    elements.append(Spacer(1, 10))

    # Weaknesses
    elements.append(Paragraph("<b>Weaknesses:</b>", styles["Heading3"]))
    for w in report_doc.get("weaknesses", []):
        elements.append(Paragraph(f"- {w}", styles["NormalSmall"]))
    elements.append(Spacer(1, 10))

    # Difficulty Summary
    elements.append(Paragraph("<b>Performance by Difficulty:</b>", styles["Heading3"]))
    diff_data = [["Difficulty", "Count", "Avg Score"]]
    for level, stats in report_doc.get("difficulty_summary", {}).items():
        diff_data.append([level.title(), stats["count"], stats["avg_score"]])
    diff_table = Table(diff_data, hAlign="CENTER", colWidths=[120, 120, 120])
    diff_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black)
    ]))
    elements.append(diff_table)
    elements.append(Spacer(1, 20))

    # Plagiarism Summary
    elements.append(Paragraph("<b>Plagiarism Summary:</b>", styles["Heading3"]))
    plag_data = [["Status", "Count"]]
    for status, count in report_doc.get("plagiarism_summary", {}).items():
        plag_data.append([status.title(), count])
    plag_table = Table(plag_data, hAlign="CENTER", colWidths=[200, 200])
    plag_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black)
    ]))
    elements.append(plag_table)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
