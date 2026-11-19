"""
Streamlit dashboard for the Job Market Skills-Demand Pipeline.

Reads directly from PostgreSQL (DATABASE_URL env var) and shows which
skills appear most often across currently-loaded job postings, with
filters for location and remote-only. This is the "internal tool for
analysts" layer several postings ask for as a nice-to-have.

Run locally with:  streamlit run dashboard/app.py
"""

import os

import pandas as pd
import psycopg2
import streamlit as st

st.set_page_config(page_title="Job Market Skills Demand", layout="wide")


@st.cache_data(ttl=300)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        st.error("DATABASE_URL is not set. See .env.example.")
        st.stop()

    conn = psycopg2.connect(database_url)
    try:
        jobs_df = pd.read_sql("SELECT * FROM jobs ORDER BY created_at DESC", conn)
        skills_df = pd.read_sql("SELECT * FROM job_skills", conn)
    finally:
        conn.close()
    return jobs_df, skills_df


st.title("Job Market Skills-Demand Dashboard")
st.caption("Which skills show up most often in currently loaded job postings.")

jobs_df, skills_df = load_data()

if jobs_df.empty:
    st.info("No data loaded yet. Run `python src/pipeline.py` to populate the database.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    locations = ["All"] + sorted(jobs_df["location"].dropna().unique().tolist())
    location_filter = st.selectbox("Location", locations)
with col2:
    remote_only = st.checkbox("Remote only")

filtered_jobs = jobs_df.copy()
if location_filter != "All":
    filtered_jobs = filtered_jobs[filtered_jobs["location"] == location_filter]
if remote_only:
    filtered_jobs = filtered_jobs[filtered_jobs["remote"]]

filtered_skills = skills_df[skills_df["job_id"].isin(filtered_jobs["job_id"])]

st.metric("Job postings in view", len(filtered_jobs))

if not filtered_skills.empty:
    skill_counts = (
        filtered_skills["skill"]
        .value_counts()
        .rename_axis("skill")
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(20)
    )
    st.subheader("Top skills requested")
    st.bar_chart(skill_counts.set_index("skill"))
else:
    st.info("No skill matches for the current filter.")

st.subheader("Job postings")
st.dataframe(
    filtered_jobs[["title", "company_name", "location", "remote", "created_at", "url"]],
    use_container_width=True,
)
