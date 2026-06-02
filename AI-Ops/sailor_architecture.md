# Sailor Recommendation POC — Technical Documentation

## Overview

A parallel batch inference pipeline that generates structured, per-guest AI recommendations using **Gemini 2.5 Flash** (via Vertex AI) against a BigQuery guest profile dataset. Designed for high-throughput processing of large guest populations with consistent, structured output for crew and sales use.

---

## Problem Statement

Without automated guest intelligence:

* Crew lack actionable pre-sail context per guest
* Upsell opportunities identified manually or not at all
* No consistent loyalty/behavioural segmentation at scale
* Recommendations vary by individual analyst interpretation

---

## Solution

An AI-driven batch pipeline that:

* Reads guest voyage profiles from BigQuery
* Generates structured, 3-sentence recommendations per guest using Gemini
* Outputs typed, validated JSON (Pydantic schema)
* Writes results back to BigQuery for downstream consumption
* Processes thousands of guests in parallel via `ThreadPoolExecutor`

---

## High-Level Architecture

```
BigQuery
(guest voyage profile dataset)
        │
        ▼
  fetch_sailors()
  (configurable batch size)
        │
        ▼
  ThreadPoolExecutor
  (20 parallel workers)
        │
        ▼
  Gemini 2.5 Flash — Vertex AI
  (structured JSON, thinking_budget=0)
        │
        ▼
  SailorRecommendation
  (Pydantic-validated schema)
        │
        ▼
  BigQuery output table
  (sailor_recommendations)
```

---

## Detailed Workflow

### Step 1: Profile Fetch

* Connects to BigQuery using Application Default Credentials
* Pulls a configurable batch of guest profiles (`BATCH_SIZE`, default: 100)
* Selects only the columns required for inference — no PII beyond identifiers

**Columns used:**
```
sailor_id, voyage_count, days_since_last_sail,
loyalty_tier, avg_spend_per_voyage, bar_spend_index,
excursion_spend_index, cabin_category, home_country,
party_size, net_revenue_lifetime
```

---

### Step 2: Parallel Inference

Each guest profile dispatched to a `ThreadPoolExecutor` worker:

```
ThreadPoolExecutor(max_workers=20)
  └── generate_recommendation(sailor_profile)
        └── Gemini 2.5 Flash (Vertex AI)
              └── response_mime_type = "application/json"
              └── thinking_budget = 0  (throughput mode)
              └── temperature = 0.2
```

Workers process independently — failures on individual records are caught, logged, and skipped without stopping the batch.

---

### Step 3: Gemini Prompt

System prompt instructs Gemini to:

* Output **only valid JSON** — no markdown, no preamble
* Follow the 3-sentence structure: **Context → Pattern → Action**
* Use only data present in the profile (no hallucination)
* Score confidence based on data completeness

---

### Step 4: Output Validation

Raw Gemini JSON response parsed and validated via Pydantic:

```python
class SailorRecommendation(BaseModel):
    sailor_id: str
    top_line: str         # one-sentence executive summary
    headline: str         # short action headline for crew
    tags: list[str]       # 3–5 categorical tags
    suggested_upsell_categories: list[str]
    loyalty_status: str | None
    confidence: float     # 0.0 – 1.0
    context_sentence: str
    pattern_sentence: str
    action_sentence: str
```

Invalid/malformed responses raise an exception — caught per-worker, not batch-wide.

---

### Step 5: Write Back to BigQuery

Validated recommendations written to output table via BigQuery streaming insert:

```
Table: {GCP_PROJECT_ID}.{BQ_DATASET}.sailor_recommendations
```

---

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `sailor_id` | string | Guest identifier |
| `top_line` | string | One-sentence executive summary |
| `headline` | string | Short action headline for crew/sales |
| `tags` | list | 3–5 categorical tags |
| `suggested_upsell_categories` | list | Ranked upsell opportunities |
| `loyalty_status` | string / null | Derived loyalty tier |
| `confidence` | float | Model confidence 0–1 |
| `context_sentence` | string | Background context |
| `pattern_sentence` | string | Observed behavioural patterns |
| `action_sentence` | string | Recommended crew action |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| LLM | Gemini 2.5 Flash (Vertex AI) |
| LLM SDK | google-genai |
| Data Source | BigQuery |
| Output Validation | Pydantic v2 |
| Parallelism | ThreadPoolExecutor |
| Deployment | Cloud Run Job (recommended) |

---

## Security

* GCP credentials via Application Default Credentials — no keys in code
* No raw guest data logged to stdout in production
* `.env` and credential files excluded via `.gitignore`
* BigQuery access scoped to minimum required columns

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| Gemini API error (single record) | Logged, skipped, batch continues |
| Pydantic validation failure | Logged, skipped, batch continues |
| BigQuery fetch failure | Fatal — batch aborted with error log |
| BigQuery write failure | Logged — partial results may be lost |
| All workers fail | Batch completes with 0 results, error summary logged |

---

## Performance

| Parameter | Default | Notes |
|-----------|---------|-------|
| `MAX_WORKERS` | 20 | Tune based on Vertex AI quota |
| `BATCH_SIZE` | 100 | Increase for production runs |
| `thinking_budget` | 0 | Disabled for throughput; enable for quality |
| Approx. throughput | ~500–1000 records/min | Varies by quota and profile complexity |

---

## Known Data Gaps

The following signals would improve recommendation quality and are flagged for future data sourcing:

| Gap | Impact |
|-----|--------|
| Future/upcoming bookings | Enables pre-sail timing recommendations |
| Pre-sail purchase history | Improves upsell category ranking |
| Home state / proximity flag | Enables geo-targeted offers |
| Email engagement signals | Improves channel preference inference |

---

## Production Deployment

Recommended path: **Cloud Run Job** with Cloud Scheduler trigger.

```bash
gcloud run jobs create sailor-recommendations \
  --image gcr.io/YOUR_PROJECT/sailor-rec \
  --region YOUR_REGION \
  --set-env-vars GCP_PROJECT_ID=...,BQ_DATASET=...,BQ_TABLE=...

# Schedule daily at 02:00 UTC
gcloud scheduler jobs create http sailor-rec-daily \
  --schedule "0 2 * * *" \
  --uri https://YOUR_REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT/jobs/sailor-recommendations:run \
  --oauth-service-account-email YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com
```

---

## Future Enhancements

* LangGraph agent loop for multi-step reasoning (dynamic tool calls for missing data)
* Real-time scoring via Cloud Run service (triggered per booking event)
* A/B testing framework for recommendation quality
* Feedback loop from crew actions back to model prompting
* Expand schema with voyage-specific recommendations (not just guest-level)
