"""
Power BI export stage.

Exports the Postgres data as a small, clean star schema of flat CSV
files that Power BI Desktop can read directly via Get Data > Folder,
with no Postgres/ODBC driver to install on Windows:

    powerbi/data/
        dim_jobs.csv          # one row per job posting
        fact_job_skills.csv   # bridge table: job_id, skill (many-to-many)
        dim_skills.csv        # skill -> reporting category
        dim_date.csv          # one row per calendar date in range

This is a separate, reporting-shaped model from the operational
`jobs` / `job_skills` tables load.py writes -- same reasoning as
transform.py's jobs/job_skills split: a real dimensional model (fact +
dimensions, an explicit date table instead of Power BI's auto
date-hierarchy) is what you'd actually build to report on this data,
and it's worth being able to explain in an interview.

Connection comes from DATABASE_URL, same as load.py.
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import psycopg2

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "powerbi" / "data"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("export_powerbi")

# Mirrors the grouping comments in skills_taxonomy.py, kept separate so
# that file stays a pure "skill -> regex" lookup and this stays a pure
# "skill -> reporting category" lookup.
SKILL_CATEGORY: dict[str, str] = {
    # Languages
    "Python": "Languages", "Java": "Languages", "JavaScript": "Languages",
    "TypeScript": "Languages", "SQL": "Languages", "Scala": "Languages",
    "C#": "Languages", "Go": "Languages",
    # Data engineering / ETL
    "ETL": "Data Engineering", "Spark": "Data Engineering", "Databricks": "Data Engineering",
    "Airflow": "Data Engineering", "dbt": "Data Engineering",
    "Data Warehousing": "Data Engineering", "Data Modeling": "Data Engineering",
    "Kafka": "Data Engineering",
    # Cloud
    "AWS": "Cloud", "Azure": "Cloud", "GCP": "Cloud",
    # DevOps / CI-CD
    "Docker": "DevOps", "Kubernetes": "DevOps", "CI/CD": "DevOps",
    "Terraform": "DevOps", "Jenkins": "DevOps", "GitHub Actions": "DevOps",
    # Databases
    "PostgreSQL": "Databases", "MySQL": "Databases",
    "MongoDB": "Databases", "DynamoDB": "Databases",
    # BI / Analytics
    "Power BI": "BI & Analytics", "Tableau": "BI & Analytics",
    # Web / frameworks
    "React": "Web & Frameworks", "Node.js": "Web & Frameworks",
    ".NET": "Web & Frameworks", "Spring Boot": "Web & Frameworks",
    # AI / ML
    "Machine Learning": "AI & ML", "LLM": "AI & ML", "Generative AI": "AI & ML",
    # Practices
    "Agile": "Practices", "Git": "Practices",
}


def get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. See .env.example.")
    return psycopg2.connect(database_url)


def _parse_posted_date(raw_created_at: str | None) -> str | None:
    """Arbeitnow's `created_at` arrives as a Unix timestamp (seconds);
    fall back to ISO-date parsing so a future feed change doesn't
    silently blank out every date instead of just logging a warning."""
    if not raw_created_at:
        return None
    raw_created_at = str(raw_created_at).strip()
    try:
        return datetime.fromtimestamp(int(raw_created_at), tz=UTC).date().isoformat()
    except (ValueError, OverflowError):
        try:
            return datetime.fromisoformat(raw_created_at).date().isoformat()
        except ValueError:
            log.warning("Could not parse created_at=%r into a date", raw_created_at)
            return None


def export_dim_jobs(conn, output_dir: Path) -> list[str]:
    """Writes dim_jobs.csv; returns the posted_date values found so
    export_dim_date can size the date dimension to the real data."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT job_id, title, company_name, location, remote, job_types,
                   tags, created_at, url
            FROM jobs
            ORDER BY job_id
            """
        )
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

    posted_dates: list[str] = []
    out_path = output_dir / "dim_jobs.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = columns + ["posted_date"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            record = dict(zip(columns, row))
            posted_date = _parse_posted_date(record.get("created_at"))
            record["posted_date"] = posted_date
            if posted_date:
                posted_dates.append(posted_date)
            writer.writerow(record)

    log.info("Wrote %d rows to %s", len(rows), out_path)
    return posted_dates


def export_fact_job_skills(conn, output_dir: Path) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT job_id, skill FROM job_skills ORDER BY job_id, skill")
        rows = cur.fetchall()

    out_path = output_dir / "fact_job_skills.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["job_id", "skill"])
        writer.writerows(rows)

    log.info("Wrote %d rows to %s", len(rows), out_path)


def export_dim_skills(conn, output_dir: Path) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT skill FROM job_skills ORDER BY skill")
        skills = [row[0] for row in cur.fetchall()]

    out_path = output_dir / "dim_skills.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["skill", "category"])
        for skill in skills:
            writer.writerow([skill, SKILL_CATEGORY.get(skill, "Other")])

    log.info("Wrote %d rows to %s", len(skills), out_path)


def export_dim_date(posted_dates: list[str], output_dir: Path) -> None:
    """A real date dimension table (not Power BI's auto date/time
    hierarchy), spanning the min..max posted_date actually in the data."""
    if not posted_dates:
        log.warning("No posted_date values found; skipping dim_date.csv")
        return

    start = date.fromisoformat(min(posted_dates))
    end = date.fromisoformat(max(posted_dates))

    out_path = output_dir / "dim_date.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "year", "month", "month_name", "week", "day_name"])
        d = start
        while d <= end:
            writer.writerow(
                [d.isoformat(), d.year, d.month, d.strftime("%B"), d.isocalendar()[1], d.strftime("%A")]
            )
            d += timedelta(days=1)

    log.info("Wrote date dimension %s..%s to %s (%d days)", start, end, out_path, (end - start).days + 1)


def export(output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        posted_dates = export_dim_jobs(conn, output_dir)
        export_fact_job_skills(conn, output_dir)
        export_dim_skills(conn, output_dir)
        export_dim_date(posted_dates, output_dir)
    finally:
        conn.close()
    log.info("Power BI export complete -> %s", output_dir)


if __name__ == "__main__":
    try:
        export()
    except Exception:  # pragma: no cover - top-level CLI guard
        log.exception("Power BI export failed")
        sys.exit(1)
