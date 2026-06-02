"""
Sailor Recommendation POC
LangGraph-Agents / Vertex AI + Gemini

Generates structured per-sailor recommendations from a BigQuery dataset
using Gemini via the Vertex AI / google-genai SDK, with parallel processing
via ThreadPoolExecutor.

Environment variables (see .env.example):
  GCP_PROJECT_ID        — Google Cloud project ID
  VERTEX_LOCATION       — Vertex AI region (e.g. us-central1)
  GEMINI_MODEL          — Model name (default: gemini-2.5-flash)
  BQ_DATASET            — BigQuery dataset ID
  BQ_TABLE              — BigQuery table/view name
  MAX_WORKERS           — ThreadPoolExecutor parallelism (default: 20)
  BATCH_SIZE            — Rows to process per run (default: 100)
  OUTPUT_TABLE          — BigQuery table to write results to
"""

import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.bq_client import fetch_sailors, write_recommendations
from app.recommender import generate_recommendation
from app.schema import SailorRecommendation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "20"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))


def run_batch(limit: int = BATCH_SIZE) -> list[SailorRecommendation]:
    """
    Fetch a batch of sailor profiles from BigQuery and generate
    recommendations in parallel using Gemini.
    """
    logger.info(f"Fetching {limit} sailor profiles from BigQuery...")
    sailors = fetch_sailors(limit=limit)
    logger.info(f"Processing {len(sailors)} sailors with {MAX_WORKERS} workers...")

    results: list[SailorRecommendation] = []
    errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_sailor = {
            executor.submit(generate_recommendation, sailor): sailor
            for sailor in sailors
        }
        for future in as_completed(future_to_sailor):
            sailor = future_to_sailor[future]
            try:
                rec = future.result()
                results.append(rec)
            except Exception as e:
                errors += 1
                logger.warning(f"Failed for sailor {sailor.get('sailor_id', '?')}: {e}")

    logger.info(f"Completed: {len(results)} successes, {errors} errors.")
    return results


def main():
    recommendations = run_batch()

    # Write back to BigQuery
    if recommendations:
        write_recommendations(recommendations)

    # Also dump a local sample for inspection
    sample = [r.model_dump() for r in recommendations[:5]]
    print(json.dumps(sample, indent=2, default=str))


if __name__ == "__main__":
    main()
