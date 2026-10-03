"""OPTIONAL: standalone Streamlit view of a signed-in user's EduGenie progress.

Install Streamlit separately, then run: streamlit run dashboard.py
The main app already includes this personal dashboard in its web interface.
"""
import streamlit as st

from app import database

st.set_page_config(page_title="EduGenie Dashboard", page_icon="🧠")
st.title("Your EduGenie Dashboard 🧠")
database.init_db()

if "session_token" not in st.session_state:
    st.session_state.session_token = None

if not st.session_state.session_token:
    with st.form("sign-in"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        credentials = database.login_user(email.strip().lower(), password)
        if credentials is None:
            st.error("Email or password is incorrect.")
        else:
            _, st.session_state.session_token = credentials
            st.rerun()
    st.stop()

user = database.get_user_for_session(st.session_state.session_token)
if user is None:
    st.session_state.session_token = None
    st.warning("Your session expired. Sign in again.")
    st.rerun()

st.caption(user["email"])
if st.button("Sign out"):
    database.revoke_session(st.session_state.session_token)
    st.session_state.session_token = None
    st.rerun()

data = database.dashboard_data(user["id"])
col1, col2, col3 = st.columns(3)
col1.metric("Learning activities", data["requests"])
col2.metric("Quizzes completed", data["quizzes"])
col3.metric("Average quiz score", f'{data["average_score"]}%')

st.subheader("Recent learning")
if data["history"]:
    st.dataframe(data["history"], use_container_width=True, hide_index=True)
else:
    st.info("Your learning activity will appear here.")

st.subheader("Recent quiz scores")
if data["quiz_results"]:
    st.dataframe(data["quiz_results"], use_container_width=True, hide_index=True)
else:
    st.info("Finish a quiz in EduGenie to see your score here.")
