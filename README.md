# Job Market Skills-Demand Pipeline

An ETL pipeline that pulls live job postings, detects which technical
skills they ask for, loads the results into PostgreSQL, and surfaces the
findings in a small dashboard — built to track the exact question every
job search eventually asks: **what skills are actually in demand right
now?**

## Why this project exists

Built to close a specific, recurring gap: job postings in data/IT roles
kept asking for ETL pipeline and CI/CD experience that hadn't been
demonstrated anywhere outside coursework. Rather than list those as
"interests" on a CV, this project is a real, working instance of both —
plus the project's own subject (what skills recruiters ask for) turned
the exercise into something directly useful for a live job search.

## Architecture

```
            ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
            │   extract   │ --> │  transform   │ --> │     load    │
            │ (Arbeitnow  │     │ (skill regex │     │ (PostgreSQL │
            │  public API)│     │  detection)  │     │   upsert)   │
            └─────────────┘     └──────────────┘     └──────┬──────┘
                                                             │
                                                     ┌───────▼────────┐
                                                     │ Streamlit      │
                                                     │ dashboard      │
                                                     └────────────────┘
```

- **Extract** (`src/extract.py`) — paginates through the
  [Arbeitnow public job board API](https://www.arbeitnow.com/api/job-board-api)
  (no API key required), with retries and a page cap, and writes the raw
  JSON response to `data/raw/` unmodified. Keeping the raw payload means
  transform logic can be fixed and re-run without re-hitting the API.
- **Transform** (`src/transform.py`) — normalizes each posting into a
  `jobs` record, and scans the title/tags/description against a skills
  taxonomy (`src/skills_taxonomy.py`) to produce a long-format
  `job_skills` table (one row per job-skill match). Two tables because
  skills-per-job is many-to-many — a comma-separated column would work
  until you needed to `GROUP BY skill`.
- **Load** (`src/load.py`) — upserts both tables into PostgreSQL
  (`ON CONFLICT DO UPDATE` / `DO NOTHING`), so re-running the pipeline on
  overlapping data is safe rather than duplicating rows.
- **Dashboard** (`dashboard/app.py`) — a Streamlit app reading directly
  from Postgres, showing the most-requested skills with location/remote
  filters.
- **Power BI export** (`src/export_powerbi.py`) — exports the same data
  as a small star schema (fact + dimension CSVs, including a real date
  table) for a Power BI Desktop report. See [POWERBI.md](POWERBI.md).

## Running it locally

Requires Docker.

```bash
cp .env.example .env         # only needed if you run scripts outside Docker
docker compose up --build    # starts Postgres, runs the pipeline once, starts the dashboard
```

Then open http://localhost:8501 for the dashboard.

To re-run just the pipeline (e.g. to refresh the data) without restarting
everything:

```bash
docker compose run --rm pipeline
```

To (re)generate the Power BI CSV extracts in `powerbi/data/`:

```bash
docker compose run --rm powerbi-export
```

See [POWERBI.md](POWERBI.md) for building the actual report in Power BI
Desktop on top of these files.

### Running without Docker

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://jobs_user:jobs_password@localhost:5432/jobs_db
cd src && python pipeline.py
```

## Testing

```bash
pip install -r requirements.txt
pytest -v
```

- `test_extract.py` and `test_transform.py` are pure unit tests — all
  HTTP calls are mocked, so they run anywhere with no network and no
  database.
- `test_load.py` is an integration test against a real Postgres; it's
  automatically skipped unless `DATABASE_URL` is set (see its docstring).
  CI sets this via a Postgres service container, so it genuinely runs
  there — it isn't just skipped silently in practice.

## CI/CD (`.github/workflows/ci.yml`)

Two jobs:

1. **`test`** — runs on every push and pull request: spins up a Postgres
   service container, lints with `ruff`, and runs the full test suite
   (unit + the Postgres integration test). This is the CI half: nothing
   merges without green tests.
2. **`run-pipeline`** — runs on a daily schedule (06:17 UTC) and can also
   be triggered manually from the Actions tab. It builds the project and
   runs the real pipeline end-to-end against the **live** Arbeitnow API,
   not fixture data. This is the CD/automation half.

**Known limitation, by design:** the scheduled job's Postgres is an
ephemeral service container scoped to that one workflow run, so data
doesn't accumulate across scheduled runs in this default setup — each
run is a fresh, full validation of the pipeline end-to-end. For a version
that actually accumulates history, point `DATABASE_URL` (as a GitHub
Actions secret) at a persistent hosted Postgres instance (e.g. a free-tier
Neon or Supabase database) instead of the service container — no code
changes needed, since `load.py` already reads the connection string from
`DATABASE_URL`.

## Skills demonstrated

Python · SQL · ETL pipeline design · data modelling (jobs / job_skills
junction table; a separate fact/dimension star schema with a real date
table for reporting) · PostgreSQL · Docker & docker-compose · CI/CD
(GitHub Actions, scheduled + on-push) · automated testing (unit +
integration) · data visualization (Streamlit; Power BI with DAX
measures).

## Project structure

```
job-market-skills-pipeline/
├── src/
│   ├── extract.py          # pulls raw postings from the API
│   ├── transform.py        # normalizes + detects skills
│   ├── load.py              # upserts into PostgreSQL
│   ├── pipeline.py          # orchestrates extract -> transform -> load
│   ├── skills_taxonomy.py   # the skill-keyword dictionary
│   └── export_powerbi.py   # exports a star schema for Power BI
├── sql/schema.sql           # jobs + job_skills table definitions
├── dashboard/app.py         # Streamlit dashboard
├── powerbi/                 # Power BI CSV extracts + the .pbix report
├── tests/                   # unit + integration tests, with fixtures
├── Dockerfile
├── docker-compose.yml
├── POWERBI.md               # building the Power BI report, step by step
└── .github/workflows/ci.yml # CI (tests) + CD (scheduled live pipeline run)
```
