# KYS MCP Server — Technical Documentation

## Overview

KYS (Know Your Sailor) is a **Model Context Protocol (MCP)** server that exposes a Looker/BigQuery semantic layer as AI-queryable tools. It enables LLM clients (Claude, ChatGPT, and custom agents) to query governed guest voyage data through typed, validated tool calls — with canonical business filters applied automatically to every query.

---

## Problem Statement

Without a governed query layer for AI:

* LLMs query raw tables directly, bypassing business logic
* Canonical filters (commercial flag, status, charter exclusion) inconsistently applied
* No semantic layer — field names and metric definitions vary by query author
* Ungoverned access exposes sensitive data to LLM context windows

---

## Solution

An MCP server that:

* Exposes exactly two tools — query and discover
* Enforces canonical net bookings filters on every query automatically
* Proxies all requests through the Looker semantic layer (LookML)
* Validates inputs and returns structured, typed responses
* Sits between the LLM and BigQuery — no direct table access

---

## High-Level Architecture

```
LLM Client (Claude / ChatGPT / Agent)
        │
        │  MCP tool call (JSON)
        ▼
┌─────────────────────────────────┐
│   KYS MCP Server — FastAPI      │
│                                 │
│  GET  /tools        (discover)  │
│  POST /tools/call   (execute)   │
│  GET  /health                   │
└──────────────┬──────────────────┘
               │
               ▼
        Looker API
    (LookML semantic layer)
               │
               ▼
          BigQuery
  (guest voyage profile dataset)
               │
               ▼
        Azure Entra ID / IAM
     (identity & access control)
```

---

## Detailed Workflow

### Step 1: Tool Discovery

LLM client calls `GET /tools` to discover available tools and their input schemas.

Server returns:
* `query_sailor_profile` — parameterised query tool
* `get_field_catalog` — field discovery tool

LLM uses schema to construct valid tool calls without hardcoded field knowledge.

---

### Step 2: Tool Call — `query_sailor_profile`

LLM sends a `POST /tools/call` with:

```json
{
  "name": "query_sailor_profile",
  "arguments": {
    "dimensions": ["sailor_voyage_profile.loyalty_tier"],
    "measures": ["sailor_voyage_profile.net_bookings"],
    "filters": {},
    "limit": 500,
    "ytd_only": true
  }
}
```

---

### Step 3: Canonical Filter Injection

Server merges LLM-supplied filters with the canonical net bookings filter set:

```
commercial_flag   = "Y"
status            = "BK,CL,TM"     (net bookings cohort)
is_real_voyage    = "Yes"
rm_charter_flag   = "-Planned"     (charter exclusion)
res_bk_trans_date = YTD range      (when ytd_only=true)
```

> **Filter syntax note:** Looker commas mean OR for positive filters and AND for negated filters. `"-Planned,-NULL"` is a known trap that accidentally ANDs the exclusions and returns incorrect charter rows. This server handles exclusions correctly with separate negated values.

LLM-supplied filters are merged on top — they cannot override the canonical set.

---

### Step 4: Looker Query Execution

Merged filters and fields dispatched to Looker API:

```
POST /api/4.0/queries/run/json
Body: WriteQuery {
  model:   LOOKER_MODEL,
  view:    LOOKER_EXPLORE,
  fields:  [dimensions + measures],
  filters: {canonical + user filters},
  limit:   500
}
```

Results returned as JSON array.

---

### Step 5: Response to LLM

```json
{
  "row_count": 12,
  "filters_applied": {
    "commercial_flag": "Y",
    "status": "BK,CL,TM",
    "is_real_voyage": "Yes",
    "rm_charter_flag": "-Planned",
    "res_bk_trans_date": "2025-01-01 to 2025-06-01"
  },
  "data": [
    { "sailor_voyage_profile.loyalty_tier": "Gold", "sailor_voyage_profile.net_bookings": 1420 },
    ...
  ]
}
```

---

## Available Tools

### `query_sailor_profile`

Query the sailor voyage profile with governed filters auto-applied.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dimensions` | array | ✅ | LookML fields to group by |
| `measures` | array | ✅ | LookML fields to aggregate |
| `filters` | object | ❌ | Additional filters (merged with canonical) |
| `limit` | integer | ❌ | Max rows (default: 500) |
| `ytd_only` | boolean | ❌ | Scope to YTD dates (default: true) |

---

### `get_field_catalog`

Returns all dimensions and measures available in the explore. Use to discover valid field names before querying.

No input parameters required.

---

## Canonical Filter Reference

| Filter | Value | Purpose |
|--------|-------|---------|
| `commercial_flag` | `Y` | Exclude internal/test bookings |
| `status` | `BK,CL,TM` | Net bookings transaction cohort |
| `is_real_voyage` | `Yes` | Exclude placeholder voyages |
| `rm_charter_flag` | `-Planned` | Exclude charter voyages |
| `res_bk_trans_date` | YTD range | Scope to current year (ytd_only) |

**Active book vs net bookings cohort:**
* `status = "BK"` — active bookings only (~25% fewer rows)
* `status = "BK,CL,TM"` — full net bookings transaction cohort

These are semantically different and produce materially different results. The default is the net bookings cohort.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| API Framework | FastAPI |
| MCP Protocol | REST (JSON tool schema) |
| Semantic Layer | Looker (LookML) |
| Data Warehouse | BigQuery |
| Auth | API Key + OAuth 2.0 (Looker) |
| Deployment | Google Cloud Run |

---

## Security

* MCP server auth via `X-API-Key` header
* Looker API auth via OAuth 2.0 (client ID + secret)
* Canonical filters cannot be bypassed by LLM tool calls
* No raw BigQuery access — all queries via Looker semantic layer
* Secrets managed via Cloud Run environment variables
* `looker.ini` and credential files excluded via `.gitignore`

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| Invalid API key | `401 Unauthorized` |
| Unknown tool name | `404 Not Found` |
| Looker query failure | `500` with error message |
| Invalid field name | Looker API error propagated to client |
| Field catalog unavailable | `500` with error message |

---

## Connecting to Claude

Once deployed to Cloud Run, register as an MCP server in Claude:

```
Server URL:  https://your-cloud-run-url
Auth header: X-API-Key: your_mcp_api_key
```

Claude will call `GET /tools` on connection to discover available tools and their schemas.

---

## Deployment

```bash
gcloud run deploy kys-mcp \
  --source . \
  --region YOUR_REGION \
  --set-env-vars \
    MCP_API_KEY=...,\
    LOOKER_BASE_URL=...,\
    LOOKER_CLIENT_ID=...,\
    LOOKER_CLIENT_SECRET=...,\
    LOOKER_MODEL=...,\
    LOOKER_EXPLORE=...
```

---

## Future Enhancements

* Write tool — governed DML operations back to BigQuery
* Multi-explore support (revenue analytics, pre-sail, on-board spend)
* Row-level security per requesting user identity
* Query result caching for high-frequency dimension queries
* Integration with approval workflow for sensitive data access
