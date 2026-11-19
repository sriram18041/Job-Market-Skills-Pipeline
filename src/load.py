"""
Load stage.

Loads the transformed jobs.csv / job_skills.csv into PostgreSQL.
Idempotent: re-running with the same job_id upserts rather than
duplicating (ON CONFLICT DO UPDATE / DO NOTHING), so the pipeline is
safe to run on a schedule against overlapping pages of the source feed.

Connection comes from the DATABASE_URL env var, e.g.:
    postgresql://jobs_user:jobs_password@localhost:5432/jobs_db
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

DEFAULT_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("load")


def get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. See .env.example.")
    return psycopg2.connect(database_url)


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text())
    conn.commit()


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_jobs(conn, jobs_rows: list[dict]) -> int:
    if not jobs_rows:
        return 0
    sql = """
        INSERT INTO jobs (job_id, title, company_name, location, remote, job_types, tags, created_at, url)
        VALUES (%(job_id)s, %(title)s, %(company_name)s, %(location)s, %(remote)s, %(job_types)s, %(tags)s, %(created_at)s, %(url)s)
        ON CONFLICT (job_id) DO UPDATE SET
            title = EXCLUDED.title,
            company_name = EXCLUDED.company_name,
            location = EXCLUDED.location,
            remote = EXCLUDED.remote,
            job_types = EXCLUDED.job_types,
            tags = EXCLUDED.tags,
            created_at = EXCLUDED.created_at,
            url = EXCLUDED.url;
    """
    for row in jobs_rows:
        row["remote"] = str(row.get("remote", "")).strip().lower() in ("true", "1", "yes")
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, jobs_rows)
    conn.commit()
    return len(jobs_rows)


def load_job_skills(conn, skill_rows: list[dict]) -> int:
    if not skill_rows:
        return 0
    sql = """
        INSERT INTO job_skills (job_id, skill)
        VALUES (%(job_id)s, %(skill)s)
        ON CONFLICT (job_id, skill) DO NOTHING;
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, skill_rows)
    conn.commit()
    return len(skill_rows)


def load(jobs_csv: Path, skills_csv: Path) -> None:
    jobs_rows = _read_csv(jobs_csv)
    skill_rows = _read_csv(skills_csv)

    conn = get_connection()
    try:
        ensure_schema(conn)
        n_jobs = load_jobs(conn, jobs_rows)
        n_skills = load_job_skills(conn, skill_rows)
        log.info("Loaded %d jobs and %d job-skill rows into Postgres", n_jobs, n_skills)
    finally:
        conn.close()


if __name__ == "__main__":
    jobs_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PROCESSED_DIR / "jobs.csv"
    skills_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PROCESSED_DIR / "job_skills.csv"
    try:
        load(jobs_path, skills_path)
    except Exception:  # pragma: no cover - top-level CLI guard
        log.exception("Load stage failed")
        sys.exit(1)
