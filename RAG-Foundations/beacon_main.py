"""
Beacon Knowledge Agent — RAG-Foundations
Cloud Run REST API for document search and retrieval with citation support.

Environment variables (see .env.example):
  BEACON_API_KEY         — API key for authenticating requests
  GCP_PROJECT_ID         — Google Cloud project ID
  FIRESTORE_COLLECTION   — Firestore collection name for sessions/analytics
  VERTEX_LOCATION        — Vertex AI region (e.g. us-east4)
  SEARCH_ENGINE_ID       — Vertex AI Search engine/datastore ID
  RATE_LIMIT_PER_MINUTE  — Max requests per API key per minute (default: 60)
"""

import os
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from app.search import search_knowledge_base
from app.sessions import log_session
from app.utils import format_citations

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("BEACON_API_KEY", "")
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))

# ---------------------------------------------------------------------------
# Rate limiting (in-memory; use Redis for multi-instance production)
# ---------------------------------------------------------------------------
request_counts: dict[str, list[float]] = defaultdict(list)

def check_rate_limit(api_key: str) -> bool:
    now = time.time()
    window = 60
    request_counts[api_key] = [t for t in request_counts[api_key] if now - t < window]
    if len(request_counts[api_key]) >= RATE_LIMIT:
        return False
    request_counts[api_key].append(now)
    return True

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Beacon Knowledge Agent",
    description="RAG-powered knowledge search API with session tracking and citations.",
    version="3.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server API key not configured.")
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    if not check_rate_limit(api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")
    return api_key

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    top_k: int = 5
    recency_days: Optional[int] = None  # filter results to last N days

class SearchResponse(BaseModel):
    query: str
    answer: str
    citations: list[dict]
    session_id: Optional[str]
    timestamp: str

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/search", response_model=SearchResponse, dependencies=[Depends(verify_api_key)])
async def search_post(body: SearchRequest, request: Request):
    """ChatGPT-compatible POST endpoint."""
    return await _handle_search(body)


@app.get("/search", response_model=SearchResponse, dependencies=[Depends(verify_api_key)])
async def search_get(query: str, session_id: Optional[str] = None, top_k: int = 5):
    """Claude-compatible GET endpoint."""
    body = SearchRequest(query=query, session_id=session_id, top_k=top_k)
    return await _handle_search(body)


@app.post("/", response_model=SearchResponse, dependencies=[Depends(verify_api_key)])
async def search_legacy(body: SearchRequest):
    """Legacy POST endpoint for backwards compatibility."""
    return await _handle_search(body)


async def _handle_search(body: SearchRequest) -> SearchResponse:
    logger.info(f"Search query: '{body.query}' | session: {body.session_id}")
    try:
        results = await search_knowledge_base(
            query=body.query,
            top_k=body.top_k,
            recency_days=body.recency_days,
        )
        answer, citations = format_citations(body.query, results)
        await log_session(
            session_id=body.session_id,
            query=body.query,
            result_count=len(citations),
        )
        return SearchResponse(
            query=body.query,
            answer=answer,
            citations=citations,
            session_id=body.session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed. Check server logs.")
