"""
query.py
--------
The API endpoints.

  POST /api/query      ask a question, get SQL + results + an insight
  GET  /api/health     is the service alive and is the database reachable
  GET  /api/examples   sample questions for the UI sidebar
"""

import logging

import mysql.connector
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.agents.insights_agent import generate_insight
from app.agents.sql_agent import CannotAnswerError, generate_sql, repair_sql
from app.config import get_settings
from app.db.connection import check_database, run_select
from app.utils.rate_limit import QUERY_RATE_LIMIT, limiter
from app.utils.sql_guard import UnsafeQueryError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# --- request and response shapes -------------------------------------------
# Pydantic models describe what goes in and what comes out. FastAPI uses them
# to validate incoming JSON automatically and to build the docs page, so a
# question that is empty or 5,000 characters long is rejected before our code
# ever sees it.

class HistoryTurn(BaseModel):
    """One earlier exchange: what was asked, and the SQL that answered it."""

    question: str = Field(..., max_length=500)
    sql: str = Field(..., max_length=4000)


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="A question about Bangalore restaurants, in plain English.",
    )
    history: list[HistoryTurn] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Recent answered turns, oldest first. Lets the agent understand "
            "follow-ups such as 'same for Koramangala' or 'what about under 500?'"
        ),
    )


class QueryResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
    insight: str
    elapsed_ms: int
    repaired: bool = False


EXAMPLE_QUESTIONS = [
    "Top 10 rated North Indian restaurants in Koramangala under 800 rupees",
    "Which area has the most restaurants offering online ordering?",
    "What is the average cost for two across different cuisines?",
    "Do restaurants with table booking have higher ratings?",
    "Best value for money restaurants with at least 500 votes",
    "Which cuisines are rated highest in Indiranagar?",
    "Compare cafes, pubs and fine dining on rating and cost",
    "Most expensive areas to eat in Bangalore",
    "Which restaurants cost more than 2000 but rate below 3.5?",
    "How many restaurants are there in each area?",
]


@router.get("/health")
def health() -> dict:
    """
    Liveness check. Hit this first when something seems broken: it tells you
    whether the API is up, whether MySQL answers, and which model is in use.
    """
    settings = get_settings()
    database = check_database()
    return {
        "status": "ok" if database["connected"] else "degraded",
        "database": database,
        "model": settings.groq_model,
    }


@router.get("/examples")
def examples() -> dict:
    """Sample questions, shown in the UI sidebar so a new visitor has a start."""
    return {"examples": EXAMPLE_QUESTIONS}


@router.post("/query", response_model=QueryResponse)
@limiter.limit(QUERY_RATE_LIMIT)
def ask(request: Request, payload: QueryRequest) -> QueryResponse:
    """
    The main endpoint. Runs the whole pipeline:

      1. Agent 1 turns the question into SQL
      2. the safety gate refuses anything that is not a plain SELECT
      3. MySQL runs it as a read-only user
      4. if MySQL rejects it, Agent 1 gets one chance to fix its own query
      5. Agent 2 writes the plain-English summary

    'request' is unused by our code but must be here: the rate limiter needs
    it to tell visitors apart.
    """
    settings = get_settings()
    question = payload.question.strip()
    history = [turn.model_dump() for turn in payload.history]
    logger.info("question: %s  (history: %s turns)", question, len(history))

    # --- 1 and 2: generate and validate ------------------------------------
    try:
        sql = generate_sql(question, history)
    except CannotAnswerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnsafeQueryError as exc:
        logger.warning("unsafe query blocked: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=f"That question produced a query I am not allowed to run. {exc}",
        ) from exc
    except Exception as exc:                      # noqa: BLE001
        logger.exception("SQL generation failed")
        raise HTTPException(
            status_code=503,
            detail="The AI service is unavailable right now. Please try again.",
        ) from exc

    # --- 3 and 4: run it, with one repair attempt ---------------------------
    repaired = False
    try:
        result = run_select(sql, settings.max_rows_returned)
    except mysql.connector.Error as exc:
        logger.warning("MySQL rejected the query: %s", exc)
        try:
            sql = repair_sql(question, sql, str(exc))
            repaired = True
            result = run_select(sql, settings.max_rows_returned)
        except mysql.connector.Error as second_exc:
            logger.error("repair attempt also failed: %s", second_exc)
            raise HTTPException(
                status_code=422,
                detail="I could not build a working query for that question. "
                       "Try rephrasing it, or be more specific.",
            ) from second_exc
        except (UnsafeQueryError, Exception) as repair_exc:   # noqa: BLE001
            logger.error("repair failed: %s", repair_exc)
            raise HTTPException(
                status_code=422,
                detail="I could not build a working query for that question. "
                       "Try rephrasing it.",
            ) from repair_exc

    # --- 5: the plain-English summary --------------------------------------
    insight = generate_insight(question, result["columns"], result["rows"])

    return QueryResponse(
        question=question,
        sql=sql,
        columns=result["columns"],
        rows=result["rows"],
        row_count=result["row_count"],
        truncated=result["truncated"],
        insight=insight,
        elapsed_ms=result["elapsed_ms"],
        repaired=repaired,
    )
