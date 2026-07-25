"""
Page Pulse — a small URL audit tool.

POST /audit  {"url": "https://example.com"}
  -> JSON report: status, response_time_ms, title, meta_description,
     h1_count, images_missing_alt, word_count

Built for the Digital Heroes SDE qualification task.
"""

import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

app = FastAPI(title="Page Pulse")

REQUEST_TIMEOUT_SECONDS = 10.0
USER_AGENT = "PagePulse/1.0 (+https://digitalheroesco.com)"


class AuditRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def must_be_http_url(cls, v: str) -> str:
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                "URL must be a valid absolute http(s) URL, e.g. https://example.com"
            )
        return v


def parse_html_report(html: str) -> dict:
    """
    Pure parsing logic, kept separate from network I/O so it can be
    unit tested without hitting the network.
    """
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_tag.get("content", "").strip() if meta_tag else None

    h1_count = len(soup.find_all("h1"))

    images = soup.find_all("img")
    images_missing_alt = sum(
        1 for img in images if not img.get("alt", "").strip()
    )

    # Strip script/style before counting visible words
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    word_count = len([w for w in text.split() if w.strip()])

    return {
        "title": title,
        "meta_description": meta_description,
        "h1_count": h1_count,
        "images_missing_alt": images_missing_alt,
        "word_count": word_count,
    }


@app.post("/audit")
async def audit(payload: AuditRequest):
    url = payload.url
    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=408,
            content={"error": "The request timed out while fetching the URL."},
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=502,
            content={"error": "Could not connect to that URL. Check it's reachable."},
        )
    except httpx.RequestError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": f"Could not fetch URL: {exc}"},
        )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    content_type = response.headers.get("content-type", "")

    if "text/html" not in content_type:
        return JSONResponse(
            status_code=200,
            content={
                "url": url,
                "status": response.status_code,
                "response_time_ms": elapsed_ms,
                "error": f"Response was not HTML (content-type: {content_type or 'unknown'}). "
                "No page report available.",
            },
        )

    try:
        report = parse_html_report(response.text)
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": "Fetched the page but failed to parse its HTML."},
        )

    return {
        "url": url,
        "status": response.status_code,
        "response_time_ms": elapsed_ms,
        **report,
    }


# Serve the frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")