# Page Pulse

A small tool that audits any URL and reports back HTTP status, response time,
title, meta description, H1 count, images missing alt text, and approximate
word count.

Built for the Digital Heroes SDE qualification task.

Live: `<add your deployed URL here>`

## Stack

FastAPI (backend + serves the static frontend), httpx (async fetch), BeautifulSoup4 (parsing). No frontend framework — plain HTML/CSS/JS, since the UI is a single input and a report card.

## Running locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open `http://localhost:8000`.

## Running tests

```bash
pip install -r requirements.txt pytest respx
pytest tests/ -v
```

## API contract

### `POST /audit`

Request body:
```json
{ "url": "https://example.com" }
```

Success response (`200`):
```json
{
  "url": "https://example.com",
  "status": 200,
  "response_time_ms": 312.4,
  "title": "Example Domain",
  "meta_description": "...",
  "h1_count": 1,
  "images_missing_alt": 0,
  "word_count": 145
}
```

Error responses:
| Case | Status | Body |
|---|---|---|
| Malformed URL (not a valid `http(s)://` URL) | `422` | Pydantic validation error |
| Target didn't respond in time | `408` | `{"error": "The request timed out..."}` |
| Target unreachable / DNS failure | `502` | `{"error": "Could not connect to that URL..."}` |
| Response wasn't HTML (e.g. a JSON API, an image) | `200` | Status/timing still returned, plus `"error"` explaining why there's no page report — this isn't the client's fault, so it's not treated as a hard failure |
| Fetched OK but HTML failed to parse | `500` | `{"error": "...failed to parse its HTML."}` |

## Design decisions

1. **Parsing logic is a pure function (`parse_html_report`), separate from the network call.**
   This is the main reason the test suite doesn't need to mock the network for the "happy path" case — it just feeds known HTML into the parser and asserts on the output. Network-dependent behavior (timeouts, non-HTML responses) is tested separately with `respx` mocking `httpx`.

2. **A non-HTML response is a `200`, not an error.**
   If someone points Page Pulse at a JSON API or a PDF, that's not really a failure of the tool — the tool did its job (it fetched the URL and got a real status/timing back). Returning `200` with an explanatory `error` field lets the frontend show a clear message without treating it as broken.

3. **URL validation happens before any network call.**
   Using a Pydantic `field_validator` on the request model means malformed input (`"not-a-url"`) is rejected immediately with a `422`, instead of letting it fall through to `httpx` and produce a confusing low-level connection error.

## What I'd change with another day

- Cache recent audits (by URL) for a few minutes so repeated checks on the same page don't re-fetch every time.
- Add a basic rate limiter — right now nothing stops someone from hammering `/audit` with requests.
- Surface partial results when the HTML technically parses but looks malformed/truncated, instead of an all-or-nothing report.

## AI usage note

I used Claude to scaffold the initial FastAPI structure — the `/audit` endpoint, the parsing logic, and the first pass at the test suite. From there I ran it locally, tested it against real sites (including checking it correctly caught 17 images missing alt text on github.com), and changed the UI myself: swapped the color palette away from the generic blue-on-white default, added the status-code badge (color-coded by 2xx/3xx/4xx+) and the "copy report as JSON" button, since those felt like the kind of small, useful additions a real user of this tool would actually want. I also decided on my own how to handle non-HTML responses — treating them as a soft `200` with an explanatory error rather than a hard failure — since I felt that better reflected what actually went wrong (the tool did its job; the target just isn't a webpage).

---
Built for Digital Heroes Training Task