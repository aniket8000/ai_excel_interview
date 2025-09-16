# admin_app.py
import os
import pathlib
import sys
from datetime import datetime
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

# 🔥 Add backend/app to path so we can reuse utils
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR / "backend" / "app"))

from utils import generate_pdf_report  # reuse detailed candidate reports

# Load .env
FRONTEND_DIR = pathlib.Path(__file__).resolve().parents[0]
load_dotenv(dotenv_path=os.path.join(FRONTEND_DIR, ".env"))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "password")

st.set_page_config(page_title="Admin Panel - AI Excel Interviewer", page_icon="📊", layout="wide")
st.title("📊 Admin Panel - AI Excel Interviewer")

# ========== AUTH ==========
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False

if not st.session_state["admin_authenticated"]:
    st.subheader("🔐 Admin Login")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            st.session_state["admin_authenticated"] = True
            st.success("✅ Login successful")
            st.experimental_rerun()
        else:
            st.error("❌ Invalid credentials")
    st.stop()

# ========== FETCH REPORTS ==========
try:
    resp = requests.get(f"{BACKEND_URL}/admin/reports", timeout=120)  # ⏳ extended timeout
    resp.raise_for_status()
    reports = resp.json()
except Exception as e:
    st.error(f"Failed to fetch reports: {e}")
    st.stop()

df = pd.DataFrame(reports)
if df.empty:
    st.warning("No reports found in the database.")
    st.stop()

df["generated_at"] = pd.to_datetime(df["generated_at"])

# ========== FILTERS PANEL ==========
with st.expander("🔎 Filters", expanded=False):
    start_date = st.date_input("Start Date", value=None)
    end_date = st.date_input("End Date", value=None)
    candidate_filter = st.text_input("Search Candidate (optional)")

    col1, col2 = st.columns(2)
    with col1:
        apply_filter = st.button("Apply Filters")
    with col2:
        reset_filter = st.button("Reset Filters")

if "filtered_df" not in st.session_state:
    st.session_state["filtered_df"] = df.copy()

if apply_filter:
    filtered_df = df.copy()
    if start_date:
        filtered_df = filtered_df[filtered_df["generated_at"] >= pd.to_datetime(start_date)]
    if end_date:
        filtered_df = filtered_df[filtered_df["generated_at"] <= pd.to_datetime(end_date)]
    if candidate_filter.strip():
        filtered_df = filtered_df[filtered_df["candidate_name"].str.contains(candidate_filter, case=False)]
    st.session_state["filtered_df"] = filtered_df

if reset_filter:
    st.session_state["filtered_df"] = df.copy()

df = st.session_state["filtered_df"]

# ========== COMPANY-WIDE ANALYTICS ==========
st.subheader("📌 Dashboard Overview")
col1, col2 = st.columns([1, 1])  # Equal width

# Pie chart: score distribution
with col1:
    st.markdown("### 🎯 Score Distribution")
    bins = [0, 0.4, 0.7, 1.0]
    labels = ["Low (<0.4)", "Medium (0.4-0.7)", "High (>0.7)"]
    df["score_band"] = pd.cut(df["overall_score"], bins=bins, labels=labels, include_lowest=True)
    pie_data = df["score_band"].value_counts()

    fig, ax = plt.subplots(figsize=(4.5, 4.5))  # control chart size
    ax.pie(pie_data, labels=pie_data.index, autopct='%1.1f%%', startangle=90)
    ax.axis("equal")

    st.pyplot(fig, use_container_width=True)  # ✅ fixed (no height arg)

# Ranked candidates
with col2:
    st.markdown("### 🏆 Ranked Candidates")
    ranked = df.sort_values("overall_score", ascending=False)[
        ["candidate_name", "overall_score", "recommendation"]
    ]

    def highlight_scores(val):
        if isinstance(val, (int, float)):
            if val >= 0.7:
                return "background-color: #d4edda; color: #155724; font-weight: bold;"
            elif val >= 0.4:
                return "background-color: #fff3cd; color: #856404; font-weight: bold;"
            else:
                return "background-color: #f8d7da; color: #721c24; font-weight: bold;"
        return ""

    styled_ranked = ranked.style.applymap(highlight_scores, subset=["overall_score"])
    st.dataframe(
        styled_ranked,
        use_container_width=True,
        height=420
    )

# ====== CLEAN PDF for Global Rankings ======
def generate_ranked_pdf(data: pd.DataFrame) -> BytesIO:
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
    elements = []

    elements.append(Paragraph("Company-wide Candidate Rankings", styles["Title"]))
    elements.append(Spacer(1, 20))

    table_data = [["Candidate", "Score", "Recommendation"]]
    for _, row in data.iterrows():
        recommendation = Paragraph(str(row["recommendation"]), styles["Normal"])
        table_data.append([
            str(row["candidate_name"]),
            f"{row['overall_score']:.2f}",
            recommendation
        ])

    table = Table(table_data, hAlign="CENTER", colWidths=[150, 80, 220])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return buffer

st.download_button(
    "⬇️ Download Global Rankings PDF",
    data=generate_ranked_pdf(ranked),
    file_name="candidate_rankings.pdf",
    mime="application/pdf"
)

# ========== INDIVIDUAL CANDIDATE DRILL-DOWN ==========
st.subheader("🔍 Candidate Drill-down")

candidate = st.selectbox("Select Candidate", df["candidate_name"].unique())

if candidate:
    candidate_data = df[df["candidate_name"] == candidate].iloc[0]

    if isinstance(candidate_data, pd.Series):
        candidate_dict = candidate_data.to_dict()
    else:
        candidate_dict = candidate_data

    st.write(f"### {candidate_dict.get('candidate_name')} — Score: {candidate_dict.get('overall_score')} | {candidate_dict.get('recommendation')}")

    evaluations = candidate_dict.get("evaluations", [])
    if isinstance(evaluations, list):
        for idx, e in enumerate(evaluations, 1):
            st.markdown(f"**Q{idx}: {e.get('question_text', 'N/A')}**")
            st.write(f"- Answer: {e.get('answer', '')}")
            st.write(f"- Score: {e.get('score')}")
            st.write(f"- Reasoning: {e.get('reasoning')}")
            st.write(f"- Topic: {e.get('topic', 'General')}")
            st.write(f"- Plagiarism: {e.get('plagiarism_check', {}).get('status')}")

        # 📊 Compact performance breakdown
        scores = [ev.get("score", 0) for ev in evaluations]
        if scores:
            st.markdown("#### 📊 Performance Breakdown")

            low = sum(s < 0.4 for s in scores)
            medium = sum(0.4 <= s < 0.7 for s in scores)
            high = sum(s >= 0.7 for s in scores)

            categories = ["Low (<0.4)", "Medium (0.4-0.7)", "High (>0.7)"]
            values = [low, medium, high]
            colors_list = ["#f8d7da", "#fff3cd", "#d4edda"]

            fig, ax = plt.subplots(figsize=(3, 2))
            ax.bar(categories, values, color=colors_list, edgecolor="black")

            ax.set_ylabel("Count", fontsize=8)
            ax.set_title("Performance Breakdown", fontsize=10)
            ax.tick_params(axis="x", labelsize=8)
            ax.tick_params(axis="y", labelsize=8)

            plt.tight_layout()
            st.pyplot(fig, use_container_width=False)

        try:
            buffer = generate_pdf_report(candidate_dict)
            st.download_button(
                label=f"📄 Download {candidate}'s Report",
                data=buffer,
                file_name=f"{candidate}_report.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.warning(f"⚠️ PDF not available for {candidate}: {e}")
    else:
        st.warning("⚠️ No evaluations available for this candidate.")
