"""
Tests for Page Pulse.

- test_parse_html_report_happy_path: pure parsing logic on a known HTML sample
- test_audit_invalid_url: malformed URL is rejected before any network call
- test_audit_timeout: a slow/unreachable target returns a clean 408, not a crash
- test_audit_non_html_response: a non-HTML content-type is reported, not crashed on
"""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from main import app, parse_html_report

client = TestClient(app)

SAMPLE_HTML = """
<html>
  <head>
    <title>Sample Page</title>
    <meta name="description" content="A page for testing.">
  </head>
  <body>
    <h1>Welcome</h1>
    <h1>Second h1 on purpose</h1>
    <img src="a.png" alt="a good image">
    <img src="b.png">
    <p>Some visible words here to count for the word count check.</p>
    <script>console.log("should not be counted as words");</script>
  </body>
</html>
"""


def test_parse_html_report_happy_path():
    report = parse_html_report(SAMPLE_HTML)

    assert report["title"] == "Sample Page"
    assert report["meta_description"] == "A page for testing."
    assert report["h1_count"] == 2
    assert report["images_missing_alt"] == 1  # only the second <img> lacks alt
    assert report["word_count"] > 0
    assert "console.log" not in str(report)  # script content excluded


def test_audit_invalid_url():
    response = client.post("/audit", json={"url": "not-a-valid-url"})
    # Pydantic validation failure -> 422, no network call attempted
    assert response.status_code == 422


@respx.mock
def test_audit_timeout():
    respx.get("https://slow-site.example").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    response = client.post("/audit", json={"url": "https://slow-site.example"})
    assert response.status_code == 408
    assert "timed out" in response.json()["error"].lower()


@respx.mock
def test_audit_non_html_response():
    respx.get("https://api.example/data.json").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "application/json"}, json={"ok": True}
        )
    )
    response = client.post("/audit", json={"url": "https://api.example/data.json"})
    assert response.status_code == 200
    body = response.json()
    assert "error" in body
    assert body["status"] == 200