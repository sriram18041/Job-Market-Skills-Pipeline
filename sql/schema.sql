-- Schema for the Job Market Skills-Demand Pipeline.
-- Two tables: `jobs` (one row per posting) and `job_skills` (one row per
-- job-skill match) because a job can require many skills and a skill
-- appears across many jobs -- a classic many-to-many, modelled with a
-- junction table rather than a comma-separated column so it stays
-- queryable (e.g. "top 10 skills this month" is a simple GROUP BY).

CREATE TABLE IF NOT EXISTS jobs (
    job_id       TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    company_name TEXT,
    location     TEXT,
    remote       BOOLEAN DEFAULT FALSE,
    job_types    TEXT,
    tags         TEXT,
    created_at   TEXT,
    url          TEXT,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_skills (
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    skill  TEXT NOT NULL,
    PRIMARY KEY (job_id, skill)
);

CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill);
CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location);
