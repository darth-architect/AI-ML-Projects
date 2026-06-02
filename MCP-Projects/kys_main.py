"""
KYS MCP Server — Know Your Sailor
MCP-Projects example

A Model Context Protocol (MCP) server that exposes a Looker/BigQuery semantic
layer as AI-queryable tools. Enables Claude, ChatGPT, and other LLM clients
to query the sailor voyage profile dataset through governed, typed tool calls.

Environment variables (see .env.example):
  GCP_PROJECT_ID       — Google Cloud project ID
  LOOKER_BASE_URL      — Looker instance base URL
  LOOKER_CLIENT_ID     — Looker API client ID
  LOOKER_CLIENT_SECRET — Looker API client secret
  LOOKER_MODEL         — LookML model name
  LOOKER_EXPLORE       — LookML explore name
  MCP_API_KEY          — API key for MCP server auth
"""

import os
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from app.looker_client import run_looker_query, get_explore_fields
from app.filters import build_net_bookings_filter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MCP_API_KEY = os.environ.get("MCP_API_KEY", "")

app = FastAPI(
    title="KYS MCP Server",
    description="MCP server exposing the Sailor Voyage Profile semantic layer.",
    version="1.0.0",
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_key(api_key: str = Depends(api_key_header)):
    if MCP_API_KEY and api_key != MCP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return api_key


# ---------------------------------------------------------------------------
# MCP Tool definitions
# ---------------------------------------------------------------------------

@app.get("/tools")
async def list_tools():
    """MCP: list available tools."""
    return {
        "tools": [
            {
                "name": "query_sailor_profile",
                "description": (
                    "Query the sailor voyage profile dataset. Returns aggregated metrics "
                    "such as bookings, revenue, loyalty status, and voyage history. "
                    "Applies canonical net bookings filters automatically."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dimensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "LookML dimension fields to group by (e.g. ['loyalty_tier', 'cabin_category'])",
                        },
                        "measures": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "LookML measure fields to aggregate (e.g. ['net_bookings', 'net_egtr'])",
                        },
                        "filters": {
                            "type": "object",
                            "description": "Additional filters as field:value pairs. Canonical net bookings filters applied automatically.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max rows to return (default: 500)",
                            "default": 500,
                        },
                        "ytd_only": {
                            "type": "boolean",
                            "description": "Scope results to year-to-date transaction dates (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["dimensions", "measures"],
                },
            },
            {
                "name": "get_field_catalog",
                "description": "List all available dimensions and measures in the sailor voyage profile explore.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
    }


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


@app.post("/tools/call", dependencies=[Depends(verify_key)])
async def call_tool(request: ToolCallRequest):
    """MCP: execute a tool call."""
    if request.name == "query_sailor_profile":
        return await _query_sailor_profile(**request.arguments)
    elif request.name == "get_field_catalog":
        return await _get_field_catalog()
    else:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {request.name}")


async def _query_sailor_profile(
    dimensions: list[str],
    measures: list[str],
    filters: dict = None,
    limit: int = 500,
    ytd_only: bool = True,
) -> dict:
    """Execute a governed query against the sailor voyage profile."""
    base_filters = build_net_bookings_filter(ytd_only=ytd_only)
    combined_filters = {**base_filters, **(filters or {})}

    logger.info(f"KYS query — dims: {dimensions}, measures: {measures}, filters: {combined_filters}")

    try:
        results = await run_looker_query(
            dimensions=dimensions,
            measures=measures,
            filters=combined_filters,
            limit=limit,
        )
        return {
            "row_count": len(results),
            "filters_applied": combined_filters,
            "data": results,
        }
    except Exception as e:
        logger.error(f"Looker query error: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


async def _get_field_catalog() -> dict:
    """Return available fields from the explore."""
    try:
        fields = await get_explore_fields()
        return {"fields": fields}
    except Exception as e:
        logger.error(f"Field catalog error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "server": "kys-mcp"}
