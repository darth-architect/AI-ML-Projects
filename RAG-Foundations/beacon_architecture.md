# Beacon Knowledge Agent — Technical Documentation

## Overview

Beacon is a production-grade Retrieval-Augmented Generation (RAG) API that enables AI assistants (Claude, ChatGPT, Google Chat) to search and retrieve knowledge from a governed document corpus. It exposes a REST API deployed on Google Cloud Run, backed by Vertex AI Search for document retrieval and Firestore for session analytics.

---

## Problem Statement

Without a governed knowledge layer:

* AI assistants answer from stale training data
* No citations or source traceability
* No usage analytics or session tracking
* Inconsistent answers across platforms

---

## Solution

A centralised RAG API that:

* Retrieves ranked, cited documents from a managed datastore
* Serves multiple AI platforms from a single endpoint
* Enforces API key authentication and rate limiting
* Logs all queries for analytics and continuous improvement

---

## High-Level Architecture

```
Client (ChatGPT / Claude / Google Chat / Custom)
        │
        │  HTTP  (X-API-Key header)
        ▼
┌─────────────────────────────┐
│   Cloud Run — FastAPI App   │
│                             │
│  POST /search  (ChatGPT)    │
│  GET  /search  (Claude)     │
│  POST /        (Legacy)     │
│  GET  /health               │
└────────────┬────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
Vertex AI Search   Firestore
(document retrieval) (session logs)
     │
     ▼
Cloud Storage / Data Store
(indexed document corpus)
```

---

## Detailed Workflow

### Step 1: Request Authentication

* Client sends request with `X-API-Key` header
* Server validates key against `BEACON_API_KEY` env variable
* Invalid key → `401 Unauthorized`
* Rate limit exceeded → `429 Too Many Requests`

---

### Step 2: Query Processing

* Client provides:
  * `query` — natural language search string
  * `session_id` — optional, for session continuity
  * `top_k` — number of results (default: 5)
  * `recency_days` — optional filter for recent documents

---

### Step 3: Vertex AI Search

Query dispatched to Vertex AI Search (Discovery Engine):

```
GET /projects/{project}/locations/{location}
    /collections/default_collection
    /engines/{engine_id}
    /servingConfigs/default_config:search
```

Features enabled:
* Query expansion (AUTO)
* Spell correction (AUTO)
* Recency filtering (when `recency_days` set)

---

### Step 4: Citation Formatting

Results ranked and formatted with numbered citations:

* `[1]` — highest relevance
* `[2]`, `[3]` ... descending
* Each citation includes: `title`, `snippet`, `source URL`, `publish_date`

---

### Step 5: Session Logging

Query metadata written to Firestore asynchronously:

```
Collection: beacon_sessions
Document fields:
  - session_id
  - query
  - result_count
  - timestamp
```

Non-fatal — search response is returned even if Firestore write fails.

---

### Step 6: Response Returned

```json
{
  "query": "user query",
  "answer": "Synthesised answer with [1] [2] citations",
  "citations": [
    {
      "number": 1,
      "title": "Document Title",
      "source": "https://...",
      "snippet": "Relevant excerpt...",
      "publish_date": "2024-01-01"
    }
  ],
  "session_id": "optional-id",
  "timestamp": "2025-01-01T00:00:00+00:00"
}
```

---

## API Reference

### `POST /search`
ChatGPT-compatible search endpoint.

**Headers:** `X-API-Key: your_key`

**Body:**
```json
{
  "query": "string (required)",
  "session_id": "string (optional)",
  "top_k": 5,
  "recency_days": 30
}
```

---

### `GET /search`
Claude-compatible search endpoint.

**Headers:** `X-API-Key: your_key`

**Query params:** `query`, `session_id`, `top_k`

---

### `GET /health`
No auth required. Returns server status and timestamp.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11 |
| API Framework | FastAPI |
| Server | Uvicorn (Cloud Run) |
| Document Retrieval | Vertex AI Search (Discovery Engine) |
| Session Storage | Firestore |
| Auth | API Key (X-API-Key header) |
| Deployment | Google Cloud Run |
| Container | Docker |

---

## Security

* OAuth 2.0 via Google Application Default Credentials for GCP services
* API key authentication on all search endpoints
* Secrets managed via Cloud Run environment variables (not hardcoded)
* `.env` and credential files excluded via `.gitignore`
* Rate limiting: 60 requests/minute per key (configurable)

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| Invalid API key | `401 Unauthorized` |
| Rate limit exceeded | `429 Too Many Requests` |
| Vertex AI Search failure | `500` with error logged |
| Firestore write failure | Non-fatal — search still returns |
| No results found | Empty citations, informational message returned |
| DL not found | Prompt user to re-enter |

---

## Multi-Platform Integration

| Platform | Endpoint | Auth Method |
|----------|----------|-------------|
| ChatGPT Custom GPT | `POST /search` | X-API-Key |
| Claude Connector | `GET /search` | X-API-Key |
| Google Chat | `POST /` (legacy) | X-API-Key |
| Direct API | Any | X-API-Key |

---

## Deployment

```bash
gcloud run deploy beacon-agent \
  --source . \
  --region YOUR_REGION \
  --set-env-vars BEACON_API_KEY=...,GCP_PROJECT_ID=...,SEARCH_ENGINE_ID=... \
  --no-allow-unauthenticated
```

---

## Future Enhancements

* LLM-synthesised answers (replace snippet concatenation with generative summary)
* Multi-turn conversation support with session memory
* Feedback loop — thumbs up/down per citation to improve ranking
* Admin dashboard for query analytics
* Support for additional document types (video transcripts, structured data)
