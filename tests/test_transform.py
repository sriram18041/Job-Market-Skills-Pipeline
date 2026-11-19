"""
Unit tests for the transform stage. These run entirely against the local
fixture file (tests/fixtures/sample_jobs_raw.json) -- no network calls --
so they're fast, deterministic, and safe to run in CI on every push.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from transform import detect_skills, normalize_job, transform

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_jobs_raw.json"


def test_detect_skills_finds_expected_skills():
    text = "We need Python, SQL, and ETL pipelines. Spark and Databricks a plus. Docker and CI/CD expected."
    skills = detect_skills(text)
    for expected in ["Python", "SQL", "ETL", "Spark", "Databricks", "Docker", "CI/CD"]:
        assert expected in skills, f"expected {expected} to be detected in: {skills}"


def test_detect_skills_no_false_positive_for_unrelated_text():
    skills = detect_skills("We sell artisanal bread and pastries in central Paris.")
    assert skills == []


def test_detect_skills_is_case_insensitive():
    assert "AWS" in detect_skills("experience with aws lambda")
    assert "Docker" in detect_skills("DOCKER containers in production")


def test_normalize_job_handles_missing_fields_gracefully():
    norm = normalize_job({"title": "Engineer"})
    assert norm["title"] == "Engineer"
    assert norm["company_name"] == ""
    assert norm["remote"] is False
    assert norm["job_id"]  # falls back to a stable hash-based id


def test_transform_end_to_end_on_fixture(tmp_path):
    jobs_csv, skills_csv = transform(FIXTURE_PATH, output_dir=tmp_path)

    assert jobs_csv.exists()
    assert skills_csv.exists()

    with jobs_csv.open(newline="", encoding="utf-8") as f:
        jobs_rows = list(csv.DictReader(f))
    assert len(jobs_rows) == 4

    with skills_csv.open(newline="", encoding="utf-8") as f:
        skill_rows = list(csv.DictReader(f))

    skills_for_data_engineer = {
        row["skill"] for row in skill_rows if row["job_id"] == "sample-data-engineer-1"
    }
    assert {"Python", "SQL", "ETL", "Spark", "Databricks", "Docker", "CI/CD"}.issubset(skills_for_data_engineer)

    skills_for_bi_analyst = {
        row["skill"] for row in skill_rows if row["job_id"] == "sample-bi-analyst-3"
    }
    assert {"Power BI", "Tableau", "SQL", "Data Warehousing"}.issubset(skills_for_bi_analyst)
