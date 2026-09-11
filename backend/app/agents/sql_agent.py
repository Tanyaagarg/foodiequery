"""
sql_agent.py
------------
Agent 1 of 2. Turns an English question into a MySQL SELECT statement.

"Agent" here means a small, single-purpose worker: it gets one job, one set of
instructions, and hands its answer to the next stage. Nothing mystical.

The flow:
    question  ->  schema + rules + question  ->  Groq  ->  SQL  ->  safety gate
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.config import get_settings
from app.db.schema_info import get_schema_description
from app.utils.sql_guard import UnsafeQueryError, enforce_row_limit, validate_sql

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert MySQL analyst working with a Bangalore \
restaurant database.

Your only job is to translate the user's question into ONE valid MySQL SELECT \
statement.

{schema}

OUTPUT FORMAT
-------------
Return ONLY the SQL query. No explanation, no commentary, no markdown fences, \
no trailing semicolon. If the question cannot be answered from these tables, \
return exactly: CANNOT_ANSWER
"""

_llm: ChatGroq | None = None


def get_llm(temperature: float = 0.0) -> ChatGroq:
    """
    Creates the connection to Groq once and reuses it.

    temperature controls randomness. Zero means "always pick the most likely
    next word", which is what you want for SQL: the same question should give
    the same query every time.
    """
    global _llm
    if _llm is None:
        settings = get_settings()
        _llm = ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=temperature,
            timeout=30,
            max_retries=2,
        )
        logger.info("Groq client created, model %s", settings.groq_model)
    return _llm


def message_text(response) -> str:
    """
    Pulls the plain text out of a model response.

    LangChain returns either a string or a list of content blocks depending on
    the version and the model, so we handle both rather than assume.
    """
    # .text is a property in current LangChain. Older versions made it a
    # method, so fall back to calling it only if it is not already a string.
    text = getattr(response, "text", None)
    if isinstance(text, str):
        if text.strip():
            return text
    elif callable(text):
        called = text()
        if isinstance(called, str) and called.strip():
            return called

    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    return str(content)


class CannotAnswerError(Exception):
    """The question cannot be answered from this database."""


def generate_sql(question: str) -> str:
    """
    Asks the model for a query and returns it only if it passes every check.

    Raises CannotAnswerError if the question is out of scope, or
    UnsafeQueryError if the generated SQL breaks a safety rule.
    """
    settings = get_settings()

    messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(schema=get_schema_description())),
        HumanMessage(content=question.strip()),
    ]

    response = get_llm().invoke(messages)
    raw_sql = message_text(response).strip()
    logger.info("model returned: %s", raw_sql.replace("\n", " ")[:200])

    # Reasoning-style models sometimes narrate before answering. Keep only the
    # part from the first SELECT or WITH onwards.
    if "CANNOT_ANSWER" in raw_sql.upper():
        raise CannotAnswerError(
            "That question cannot be answered from this restaurant database."
        )

    start = re.search(r"\b(select|with)\b", raw_sql, re.IGNORECASE)
    if start:
        raw_sql = raw_sql[start.start():]

    sql = validate_sql(raw_sql)                       # raises UnsafeQueryError
    sql = enforce_row_limit(sql, settings.max_rows_returned)
    return sql


def repair_sql(question: str, bad_sql: str, error_message: str) -> str:
    """
    Second chance. If MySQL rejected the query, show the model its own SQL and
    the error, and ask for a fix.

    One retry only. If the model cannot fix its mistake with the error message
    in front of it, a third attempt rarely helps and the user is left waiting.
    """
    settings = get_settings()

    messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(schema=get_schema_description())),
        HumanMessage(
            content=(
                f"Question: {question.strip()}\n\n"
                f"You wrote this query:\n{bad_sql}\n\n"
                f"MySQL rejected it with this error:\n{error_message}\n\n"
                "Return a corrected query. SQL only."
            )
        ),
    ]

    response = get_llm().invoke(messages)
    raw_sql = message_text(response).strip()
    logger.info("repair attempt: %s", raw_sql.replace("\n", " ")[:200])

    start = re.search(r"\b(select|with)\b", raw_sql, re.IGNORECASE)
    if start:
        raw_sql = raw_sql[start.start():]

    sql = validate_sql(raw_sql)
    return enforce_row_limit(sql, settings.max_rows_returned)
