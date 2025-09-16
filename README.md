# 📊 AI Excel Mock Interviewer

This project is a **mock interview platform** designed to help recruiters evaluate candidates’ Excel knowledge efficiently.  
The system provides an **AI-powered interview experience** for candidates and a **dashboard with analytics and reports** for recruiters.

---

## 📖 Project Description

- Candidates can take Excel-based mock interviews where questions are dynamically generated using AI.
- Each candidate’s answers are **evaluated automatically** on correctness, completeness, and relevance.
- Recruiters can log into the **Admin Panel** to:
  - View detailed candidate performance reports.
  - Analyze overall scores, strengths, and weaknesses.
  - Compare multiple candidates through rankings and analytics.
  - Download professional PDF reports for each candidate.

👉 This makes it easier for recruiters to identify **which candidates perform well** and who may be **best suited for the role**.

---

## ⚙️ Tech Stack

- **Backend:** FastAPI, Motor (MongoDB), OpenAI API, ReportLab
- **Frontend (Candidate + Admin):** Streamlit
- **Database:** MongoDB Atlas
- **Deployment:** Render (Backend), Streamlit Cloud (Frontend)

---

## ✨ Features

### Candidate App

- Start an AI-powered Excel interview.
- Answer questions interactively, evaluated in real-time.
- Final summary of interview performance.

### Admin Panel

- Secure login for recruiters.
- Dashboard with score distribution and rankings.
- Individual candidate drill-down with detailed evaluations.
- PDF report generation (per candidate + global rankings).

---

## 📂 Project Structure

```
ai-excel-interviewer/
│── backend/ # FastAPI backend
│ ├── app/ # Main backend code
│ ├── requirements.txt
│── frontend/ # Candidate Streamlit app
│── admin_frontend/ # Admin Streamlit app
│── README.md
```

---

## Backend Setup

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a .env file inside backend/ with your MongoDB and OpenAI keys.

Run the backend:

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Frontend Setup (Candidate App)

```
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## Admin Panel Setup

```
cd admin_frontend
pip install -r requirements.txt
streamlit run admin_app.py
```

## 🔑 Environment Variables

### Backend (`backend/.env`)

```
MONGODB_URI=your_mongo_uri
MONGO_DB_NAME=examinerDB
OPENAI_API_KEY=your_openai_api_key
PORT=8000
HOST=0.0.0.0
```

### Frontend (`frontend/.env` and `admin_frontend/.env`)

```
BACKEND_URL=https://your-backend.onrender.com
APP_NAME=AI Excel Mock Interviewer
ADMIN_USERNAME= your user name
ADMIN_PASSWORD= password
```

---

## 📋 Sample Interview Flow

1. Candidate enters their name and starts the interview.
2. AI generates Excel-related questions (theory, formulas, scenarios).
3. Candidate answers each question.
4. The system evaluates answers automatically using keyword checks, AI analysis, and plagiarism detection.
5. Recruiter accesses the Admin Panel to review reports and identify strong candidates.

---
