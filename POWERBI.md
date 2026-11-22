# Power BI dashboard

A Power BI report built on the same live job-postings data as the rest
of this project, through a proper star schema (fact + dimension tables,
a real date table) rather than one flat export — the same "would I have
to explain this design choice in an interview" bar as the rest of the
pipeline.

## Why a separate export instead of connecting Power BI to Postgres directly

Power BI Desktop *can* connect straight to PostgreSQL, but on Windows that
needs the Npgsql driver installed and configured first — exactly the kind
of extra moving part that caused the Docker/WSL setup friction earlier in
this project. Exporting to flat CSVs instead means Power BI Desktop reads
them with its built-in, driver-free Text/CSV connector, and the whole
thing works the first time.

## 1. Generate the data

From the project root, with the Postgres container already up (see the
main [README](README.md) if not):

```bash
docker compose run --rm powerbi-export
```

This runs `src/export_powerbi.py` against the database and writes four
CSVs to `powerbi/data/`:

| File | Grain | Role |
|---|---|---|
| `dim_jobs.csv` | one row per job posting | dimension |
| `fact_job_skills.csv` | one row per job–skill match | fact (the many-to-many bridge) |
| `dim_skills.csv` | one row per skill | dimension (adds a `category`, e.g. "Cloud", "DevOps") |
| `dim_date.csv` | one row per calendar day in range | date dimension |

Re-run the same command any time you want the dashboard to reflect fresh
data (after `docker compose run --rm pipeline`, or after the scheduled
GitHub Actions run) — it fully overwrites the four CSVs.

## 2. Install Power BI Desktop

Free, Windows only: <https://www.microsoft.com/en-us/power-platform/products/power-bi/desktop>
(or via the Microsoft Store). No account/license needed to build and save
a local report.

## 3. Load the four tables

1. **Get Data → Text/CSV**, select `powerbi/data/dim_jobs.csv` → Load.
2. Repeat for `fact_job_skills.csv`, `dim_skills.csv`, and `dim_date.csv`.

(Deliberately four separate imports, not the "Get Data → Folder"
connector — Folder mode would merge them into one table, which throws
away the star schema.)

Before loading, it's worth turning off Power BI's automatic date
hierarchy, since we're bringing a real date table instead: **File →
Options and settings → Options → Data Load → uncheck "Auto date/time"**.

## 4. Build the model (Model view)

Draw these relationships (drag field → field):

- `fact_job_skills[job_id]` → `dim_jobs[job_id]` (many-to-one)
- `fact_job_skills[skill]` → `dim_skills[skill]` (many-to-one)
- `dim_jobs[posted_date]` → `dim_date[date]` (many-to-one)

Then select the `dim_date` table → **Table tools → Mark as date table**,
with `date` as the date column.

This is the star schema: `fact_job_skills` in the middle, `dim_jobs` /
`dim_skills` / `dim_date` around it. It's also why `created_at` gets
converted to a clean `posted_date` column in the export rather than left
as a raw Unix timestamp — a dimension's join key should be boring.

## 5. A few measures worth adding (DAX, new measure on `fact_job_skills`)

```DAX
Total Postings = DISTINCTCOUNT(dim_jobs[job_id])

Skill Mentions = COUNTROWS(fact_job_skills)

Postings With This Skill = DISTINCTCOUNT(fact_job_skills[job_id])

% of Postings = DIVIDE([Postings With This Skill], [Total Postings])

Avg Skills per Posting = DIVIDE(COUNTROWS(fact_job_skills), DISTINCTCOUNT(fact_job_skills[job_id]))
```

`% of Postings`, filtered by skill, is the headline number: "Python
appears in 38% of postings this period."

## 6. Suggested pages

- **Overview** — KPI cards (Total Postings, distinct companies, distinct
  locations), a bar chart of top 15 skills by `Postings With This Skill`,
  slicers for location / remote / skill category.
- **Trends** — a line chart of postings over time (`dim_date[date]` on
  the axis), and the same for the 5 skills you care most about, so a
  rising/falling skill is visible, not just a snapshot count.
- **By category** — a matrix or treemap of `dim_skills[category]` →
  `skill` → `Postings With This Skill`, so "Cloud" vs "DevOps" vs
  "Data Engineering" demand is comparable at a glance.

## 7. Save it

Save the `.pbix` into the `powerbi/` folder of your local clone (e.g.
`powerbi/job-market-skills.pbix`). Power BI Desktop embeds the imported
data inside the `.pbix` at save time, so the file is self-contained —
anyone who opens it sees the real data as of that export, with no
Postgres connection required. Commit it to the repo once it's in a state
you're happy with.
