import os
import pathlib
import sys
import requests
import streamlit as st
from dotenv import load_dotenv
from requests.exceptions import Timeout, RequestException, HTTPError

# 🔥 Add backend/app to Python path so we can reuse utils.py later (for admin panel)
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR / "backend" / "app"))

# Load frontend/.env
FRONTEND_DIR = pathlib.Path(__file__).resolve().parents[0]
load_dotenv(dotenv_path=os.path.join(FRONTEND_DIR, ".env"))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
APP_NAME = os.getenv("APP_NAME", "AI Excel Mock Interviewer")

st.set_page_config(page_title=APP_NAME, page_icon="📊", layout="centered")
st.title(APP_NAME)
st.markdown("A production-ready AI system to simulate an Excel interview.")

# Init session state
if "interview_id" not in st.session_state:
    st.session_state["interview_id"] = None
    st.session_state["last_question"] = None
    st.session_state["candidate_name"] = None
    st.session_state["progress"] = ""
    st.session_state["evaluations"] = []
    st.session_state["finished"] = False
    st.session_state["report"] = None
    st.session_state["answer_key"] = "answer_area_1"
    st.session_state["candidate_name_input"] = ""  # 🔥 Added for reset handling

# Start Interview
with st.form("start_form"):
    name = st.text_input("Your full name", key="candidate_name_input", placeholder="Enter your name here...")
    started = st.form_submit_button("Start Interview")
    if started:
        if not name.strip():
            st.warning("Please enter your name")
        else:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/start",
                    json={"candidate_name": name.strip()},
                    timeout=120,  # ⏳ extended timeout
                )
                resp.raise_for_status()
                data = resp.json()

                # Reset state
                st.session_state["interview_id"] = data["id"]
                st.session_state["last_question"] = data.get("question") or "No question received"
                st.session_state["candidate_name"] = name.strip()
                st.session_state["progress"] = data.get("progress", "1/?")
                st.session_state["evaluations"] = []
                st.session_state["finished"] = False
                st.session_state["report"] = None
                st.session_state["answer_key"] = "answer_area_1"

                st.success("Interview started — answer the questions below")
            except Timeout:
                st.error("⚠️ Server took too long to respond while starting interview. Please try again.")
            except HTTPError as e:
                st.error(f"⚠️ HTTP error while starting interview: {e.response.text}")
            except RequestException as e:
                st.error(f"⚠️ Network error while starting interview: {e}")
            except Exception as e:
                st.error(f"⚠️ Unexpected error: {e}")

# Interview Flow
if st.session_state.get("interview_id") and not st.session_state["finished"]:
    st.subheader("Interview")
    st.write(f"**Candidate:** {st.session_state.get('candidate_name')}")
    st.write(f"**Progress:** {st.session_state.get('progress')}")

    # 🔥 Parse progress for percentage bar
    try:
        current, total = map(int, st.session_state["progress"].split("/"))
        percent = int((current / total) * 100)
        st.progress(percent, text=f"Progress: {percent}% ({current}/{total})")
    except Exception:
        pass

    st.write(f"**Question:** {st.session_state.get('last_question')}")

    # Answer input field
    answer = st.text_area("Your answer", height=160, key=st.session_state["answer_key"])

    if st.button("Submit Answer"):
        try:
            resp = requests.post(
                f"{BACKEND_URL}/answer/{st.session_state['interview_id']}",
                json={"answer": answer},
                timeout=120,  # ⏳ extended timeout
            )
            resp.raise_for_status()
            data = resp.json()

            # Save evaluation internally but don’t show it
            eval_block = data.get("evaluation", {})
            st.session_state["evaluations"].append(eval_block)

            # If more questions remain → auto jump
            if "next_question" in data:
                st.session_state["last_question"] = data["next_question"]
                st.session_state["progress"] = data.get("progress", "")
                st.session_state["answer_key"] = f"answer_area_{st.session_state['progress']}"
                st.experimental_rerun()
            else:
                # Finished interview
                st.session_state["finished"] = True
                st.session_state["report"] = data.get("report")
                st.experimental_rerun()

        except Timeout:
            st.error("⚠️ Server took too long to evaluate your answer. Please try again.")
        except HTTPError as e:
            st.error(f"⚠️ HTTP error: {e.response.text}")
        except RequestException as e:
            st.error(f"⚠️ Network error: {e}")
        except Exception as e:
            st.error(f"⚠️ Unexpected error: {e}")

# Final Thank You Page (no PDF)
if st.session_state.get("finished"):
    st.markdown("## Interview Complete ✅")
    st.write("🎉 Thank you for completing the interview! Your responses have been recorded.")

    # Reset
    if st.button("🔄 Start New Interview"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        # 🔥 Reset name field
        st.session_state["candidate_name_input"] = ""
        st.experimental_rerun()
