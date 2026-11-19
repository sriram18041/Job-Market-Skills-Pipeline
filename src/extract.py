"""
Extract stage.

Pulls job postings from the Arbeitnow public job board API
(https://www.arbeitnow.com/api/job-board-api) — no API key required.
The API is paginated; we follow the `links.next` field until it runs out
or a page-count cap is hit, and write the raw, unmodified responses to
disk under data/raw/. Keeping the raw payload untouched means transform
can always be re-run (or fixed and re-run) without re-hitting the API.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

API_URL = "https://www.arbeitnow.com/api/job-board-api"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MAX_PAGES = 10          # safety cap so a bug can't loop forever against a live API
REQUEST_TIMEOUT_S = 15
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_S = 2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("extract")


def _get_with_retry(url: str) -> dict:
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:  # network error, timeout, 4xx/5xx
            last_exc = exc
            log.warning("Request failed (attempt %d/%d) for %s: %s", attempt, RETRY_ATTEMPTS, url, exc)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_S * attempt)
    assert last_exc is not None
    raise last_exc


def fetch_all_pages(start_url: str = API_URL, max_pages: int = MAX_PAGES) -> list[dict]:
    """Follow pagination and return the list of raw page payloads."""
    pages: list[dict] = []
    url: str | None = start_url
    page_count = 0

    while url and page_count < max_pages:
        log.info("Fetching page %d: %s", page_count + 1, url)
        payload = _get_with_retry(url)
        pages.append(payload)
        page_count += 1

        next_url = (payload.get("links") or {}).get("next")
        url = next_url if next_url else None

    return pages


def extract(output_dir: Path = DEFAULT_OUTPUT_DIR, max_pages: int = MAX_PAGES) -> Path:
    """Fetch all pages and persist them as one timestamped raw JSON file.

    Returns the path written, so downstream stages / the pipeline runner
    know exactly which file to transform.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = fetch_all_pages(max_pages=max_pages)

    jobs: list[dict] = []
    for page in pages:
        jobs.extend(page.get("data", []))

    run_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = output_dir / f"jobs_raw_{run_ts}.json"
    out_path.write_text(json.dumps({"fetched_at": run_ts, "job_count": len(jobs), "jobs": jobs}, indent=2))

    log.info("Wrote %d raw job postings to %s", len(jobs), out_path)
    return out_path


if __name__ == "__main__":
    try:
        extract()
    except Exception:  # pragma: no cover - top-level CLI guard
        log.exception("Extract stage failed")
        sys.exit(1)
