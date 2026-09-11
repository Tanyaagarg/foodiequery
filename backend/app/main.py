"""
main.py
-------
The entry point. Creates the FastAPI application, wires everything together,
and starts up.

Run it from the backend folder with:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for an interactive page where you can
try every endpoint without writing any frontend code.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.routers import query
from app.utils.rate_limit import limiter

# --- logging ----------------------------------------------------------------
# Prints a timestamped line for every question, every generated query and every
# error. When something misbehaves, this terminal output is where you look.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("foodiequery")

settings = get_settings()

app = FastAPI(
    title="FoodieQuery API",
    description=(
        "Ask questions about 12,464 Bangalore restaurants in plain English. "
        "An AI agent writes the SQL, a safety layer checks it, MySQL runs it, "
        "and a second agent explains the answer."
    ),
    version="1.0.0",
)

app.state.limiter = limiter

# --- CORS -------------------------------------------------------------------
# A browser will not let a page at localhost:5173 call an API at localhost:8000
# unless the API says that is allowed. This is that permission slip. Without
# it the React app in Phase 6 gets blocked with no useful error.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(query.router)


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """A friendly message instead of a raw 429 when someone asks too fast."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "That is a lot of questions at once. "
                      "Give it a minute and try again."
        },
    )


@app.get("/")
def root() -> dict:
    """A signpost, so hitting the bare address is not a dead end."""
    return {
        "name": "FoodieQuery API",
        "docs": "/docs",
        "health": "/api/health",
        "ask": "POST /api/query",
    }


@app.on_event("startup")
def on_startup() -> None:
    logger.info("FoodieQuery starting")
    logger.info("  model          : %s", settings.groq_model)
    logger.info("  database       : %s:%s/%s",
                settings.db_host, settings.db_port, settings.db_name)
    logger.info("  database user  : %s", settings.read_user)
    logger.info("  rate limit     : %s", settings.rate_limit)
