@echo off
cd /d %~dp0
call venv\Scripts\activate
streamlit run app.py

streamlit run admin_app.py