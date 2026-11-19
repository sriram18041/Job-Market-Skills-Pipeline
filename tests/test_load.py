"""
Integration test for the load stage. Unlike test_extract.py / test_transform.py
(pure unit tests, no external dependencies), this one needs a real Postgres
to load into -- so it's skipped unless DATABASE_URL is set.

Locally: `docker compose up -d postgres` then export DATABASE_URL before
running pytest. In CI: the GitHub Actions workflow starts a Postgres
service container and sets DATABASE_URL for this exact job.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set -- skipping Postgres integration test (see docstring).",
)


def test_load_is_idempotent():
    import load as load_module

    conn = load_module.get_connection()
    try:
        load_module.ensure_schema(conn)

        jobs_rows = [
            {
                "job_id": "pytest-job-1",
                "title": "Test Engineer",
                "company_name": "PytestCo",
                "location": "Remote",
                "remote": "true",
                "job_types": "Full Time",
                "tags": "python,sql",
                "created_at": "2026-11-17",
                "url": "https://example.com/pytest-job-1",
            }
        ]
        skill_rows = [
            {"job_id": "pytest-job-1", "skill": "Python"},
            {"job_id": "pytest-job-1", "skill": "SQL"},
        ]

        # Run twice -- the second run must not error or duplicate rows,
        # since the whole point of ON CONFLICT upserts is a safe re-run.
        load_module.load_jobs(conn, list(jobs_rows))
        load_module.load_jobs(conn, list(jobs_rows))
        load_module.load_job_skills(conn, list(skill_rows))
        load_module.load_job_skills(conn, list(skill_rows))

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM jobs WHERE job_id = %s", ("pytest-job-1",))
            assert cur.fetchone()[0] == 1

            cur.execute("SELECT count(*) FROM job_skills WHERE job_id = %s", ("pytest-job-1",))
            assert cur.fetchone()[0] == 2

            cur.execute("DELETE FROM jobs WHERE job_id = %s", ("pytest-job-1",))
            conn.commit()
    finally:
        conn.close()
