"""
Transform stage.

Reads a raw extract file (see extract.py), normalizes each job posting
into a flat "jobs" record, and scans the title + tags + description
against SKILLS_TAXONOMY to produce a long-format "job_skills" table
(one row per job-skill match). Two tables rather than one wide table
because skills-per-job is a many-to-many relationship -- this is the
"data modelling" decision worth being able to explain in an interview.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sys
from pathlib import Path

from skills_taxonomy import SKILLS_TAXONOMY

DEFAULT_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("transform")

# Pre-compile one case-insensitive regex per skill from its surface forms.
_COMPILED_TAXONOMY: dict[str, re.Pattern] = {
    skill: re.compile("|".join(patterns), re.IGNORECASE) for skill, patterns in SKILLS_TAXONOMY.items()
}


def detect_skills(text: str) -> list[str]:
    """Return the canonical skill names found in `text`, sorted."""
    found = [skill for skill, pattern in _COMPILED_TAXONOMY.items() if pattern.search(text)]
    return sorted(found)


def _job_id(job: dict) -> str:
    # Arbeitnow postings carry a unique `slug`; fall back to a hash of the
    # title+company if a feed ever omits it, so the pipeline never crashes
    # on a single malformed record.
    slug = job.get("slug")
    if slug:
        return slug
    return str(abs(hash((job.get("title", ""), job.get("company_name", "")))))


def normalize_job(job: dict) -> dict:
    return {
        "job_id": _job_id(job),
        "title": (job.get("title") or "").strip(),
        "company_name": (job.get("company_name") or "").strip(),
        "location": (job.get("location") or "").strip(),
        "remote": bool(job.get("remote", False)),
        "job_types": ",".join(job.get("job_types") or []),
        "tags": ",".join(job.get("tags") or []),
        "created_at": job.get("created_at"),
        "url": job.get("url"),
    }


def transform(raw_path: Path, output_dir: Path = DEFAULT_PROCESSED_DIR) -> tuple[Path, Path]:
    raw = json.loads(raw_path.read_text())
    jobs_in = raw.get("jobs", [])
    log.info("Transforming %d raw job postings from %s", len(jobs_in), raw_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    jobs_rows: list[dict] = []
    skill_rows: list[dict] = []

    for job in jobs_in:
        norm = normalize_job(job)
        jobs_rows.append(norm)

        searchable_text = " ".join(
            [
                job.get("title", ""),
                job.get("description", ""),
                " ".join(job.get("tags") or []),
            ]
        )
        for skill in detect_skills(searchable_text):
            skill_rows.append({"job_id": norm["job_id"], "skill": skill})

    jobs_path = output_dir / "jobs.csv"
    skills_path = output_dir / "job_skills.csv"

    _write_csv(jobs_path, jobs_rows, fieldnames=list(jobs_rows[0].keys()) if jobs_rows else
               ["job_id", "title", "company_name", "location", "remote", "job_types", "tags", "created_at", "url"])
    _write_csv(skills_path, skill_rows, fieldnames=["job_id", "skill"])

    log.info("Wrote %d jobs to %s and %d job-skill matches to %s", len(jobs_rows), jobs_path, len(skill_rows), skills_path)
    return jobs_path, skills_path


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python transform.py <path-to-raw-json>")
        sys.exit(1)
    try:
        transform(Path(sys.argv[1]))
    except Exception:  # pragma: no cover - top-level CLI guard
        log.exception("Transform stage failed")
        sys.exit(1)
