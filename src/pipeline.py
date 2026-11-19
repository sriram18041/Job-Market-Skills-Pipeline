"""
Pipeline orchestrator: extract -> transform -> load.

This is the single entrypoint used both locally (`python src/pipeline.py`)
and by the scheduled GitHub Actions workflow (.github/workflows/ci.yml),
so there is exactly one code path for "run the whole thing", not one for
local testing and a different one for production.

Use --skip-load to run extract+transform only (useful when you don't have
a Postgres instance running, e.g. a quick local check).
"""

from __future__ import annotations

import argparse
import logging
import sys

from extract import extract
from transform import transform

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the job-market skills-demand ETL pipeline.")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages to pull from the source API.")
    parser.add_argument("--skip-load", action="store_true", help="Run extract+transform only, skip the Postgres load.")
    args = parser.parse_args()

    log.info("=== Pipeline run starting ===")

    raw_path = extract(max_pages=args.max_pages)
    jobs_csv, skills_csv = transform(raw_path)

    if args.skip_load:
        log.info("--skip-load set: skipping the load stage.")
    else:
        from load import (
            load,  # imported lazily so --skip-load works without psycopg2/Postgres present
        )
        load(jobs_csv, skills_csv)

    log.info("=== Pipeline run complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
