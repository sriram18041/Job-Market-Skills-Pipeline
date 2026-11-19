"""
Unit tests for the extract stage. All HTTP calls are mocked (monkeypatched)
so these tests never touch the real network -- they verify our pagination
and retry logic, not Arbeitnow's uptime.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import extract


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_all_pages_follows_pagination(monkeypatch):
    pages = {
        "https://api.example/page1": {
            "data": [{"slug": "a"}, {"slug": "b"}],
            "links": {"next": "https://api.example/page2"},
        },
        "https://api.example/page2": {
            "data": [{"slug": "c"}],
            "links": {"next": None},
        },
    }

    def fake_get(url, timeout):
        return _FakeResponse(pages[url])

    monkeypatch.setattr(extract.requests, "get", fake_get)

    result = extract.fetch_all_pages(start_url="https://api.example/page1")
    assert len(result) == 2
    all_jobs = [job for page in result for job in page["data"]]
    assert [j["slug"] for j in all_jobs] == ["a", "b", "c"]


def test_fetch_all_pages_respects_max_pages(monkeypatch):
    call_count = {"n": 0}

    def fake_get(url, timeout):
        call_count["n"] += 1
        return _FakeResponse({"data": [{"slug": str(call_count["n"])}], "links": {"next": "https://api.example/next"}})

    monkeypatch.setattr(extract.requests, "get", fake_get)

    result = extract.fetch_all_pages(start_url="https://api.example/start", max_pages=3)
    assert len(result) == 3


def test_get_with_retry_raises_after_exhausting_attempts(monkeypatch):
    import requests

    def always_fails(url, timeout):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(extract.requests, "get", always_fails)
    monkeypatch.setattr(extract.time, "sleep", lambda _: None)  # skip real sleeps in tests

    with pytest.raises(requests.ConnectionError):
        extract._get_with_retry("https://api.example/will-fail")


def test_extract_writes_expected_file(tmp_path, monkeypatch):
    def fake_get(url, timeout):
        return _FakeResponse({"data": [{"slug": "x", "title": "Engineer"}], "links": {"next": None}})

    monkeypatch.setattr(extract.requests, "get", fake_get)

    out_path = extract.extract(output_dir=tmp_path, max_pages=1)
    assert out_path.exists()
    assert out_path.parent == tmp_path
