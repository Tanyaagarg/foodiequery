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

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.config import get_settings
from app.db.schema_info import get_schema_description
from app.utils.sql_guard import UnsafeQueryError, enforce_row_limit, validate_sql

logger = logging.getLogger(__name__)

# How many earlier turns to replay to the model. Enough for "same but cheaper"
# to make sense, few enough that the prompt stays small and fast.
MAX_HISTORY_TURNS = 4

SYSTEM_PROMPT = """You are an expert MySQL analyst working with a Bangalore \
restaurant database.

Your only job is to translate the user's question into ONE valid MySQL SELECT \
statement.

{schema}

FOLLOW-UP QUESTIONS
-------------------
You may be shown the earlier questions in this conversation along with the SQL \
you wrote for them. Use that history to resolve short follow-ups.

  "Top rated cafes in Indiranagar"   ->  a full query
  "same for Koramangala"             ->  the same query, area swapped
  "what about under 500?"            ->  the same query, plus a price filter
  "show me 20 instead"               ->  the same query with a larger LIMIT

Always write the complete standalone query. Never write a fragment that only \
makes sense next to the previous one.

YOUR JOB IS TO ANSWER, NOT TO JUDGE THE QUESTION
------------------------------------------------
Assume every question is a reasonable one asked in a hurry. People type fast, \
misspell things, drop words, mix Hindi and English, and use no punctuation. \
None of that is a reason to refuse. Work out what they meant and answer it.

  "tell best food from best restaurants for veg"
      -> top rated restaurants with vegetarian signals, showing dish_liked
  "chepest biriyani in kormangla"
      -> biryani in Koramangala, ordered by cost ascending
  "gud place for date"
      -> fine dining with table booking, high rating
  "wanna eat something nice around indranagar"
      -> top rated restaurants in Indiranagar

Handling misspellings:
  - Never match a place, cuisine or restaurant name with = . Always use LIKE \
with wildcards on a distinctive fragment: 'Koramangla' should still find \
Koramangala via LIKE '%Koraman%'.
  - Drop the part of a word most likely to be wrong. 'biriyani', 'biryani' \
and 'briyani' all match LIKE '%iry%' poorly, so prefer a short stable stem \
such as LIKE '%Bir%'.
  - When a word could be an area, a cuisine or a restaurant name, search \
across all three with OR rather than picking one and risking nothing.

Handling parts you cannot answer:
  - If a question has several parts and only one is impossible, answer the \
rest. "best place to dine out with 9 family members" is a question about \
dine-out restaurants. Answer that and ignore the group size.
  - If the data has no exact column, use the closest available signal rather \
than refusing. Approximate answers are useful. Refusals are not.

WHEN TO GIVE UP
---------------
Only when the question is about something this data has never contained and \
there is no reasonable stand-in: opening hours, phone numbers, dish prices or \
menus, review text, or a city other than Bangalore. That is the entire list.

In that case only, reply with CANNOT_ANSWER, a colon, and one short sentence \
naming what is missing.

  CANNOT_ANSWER: The data does not include opening hours.

Never refuse because a question is vaguely worded, badly spelled, informal, \
or broader than the data. In all of those cases, answer as best you can.

OUTPUT FORMAT
-------------
Return ONLY the SQL query. No explanation, no commentary, no markdown fences, \
no trailing semicolon.
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


def extract_refusal_reason(raw: str) -> str:
    """
    Pulls the explanation out of "CANNOT_ANSWER: the data has no X".

    A refusal that does not say what is missing is close to useless. The user
    cannot tell whether they phrased it badly or asked for something the data
    has never held, so they either rephrase forever or give up.
    """
    match = re.search(r"CANNOT_ANSWER\s*[:\-]\s*(.+)", raw, re.IGNORECASE | re.DOTALL)
    if match:
        reason = match.group(1).strip().split("\n")[0].strip(' "`')
        if reason:
            # Make sure it reads as a finished sentence.
            return reason if reason.endswith((".", "!", "?")) else reason + "."

    return (
        "That needs information this dataset does not hold. It covers Bangalore "
        "restaurants only: ratings, prices, cuisines, areas, delivery and booking."
    )


def build_history_messages(history: list[dict] | None) -> list:
    """
    Replays the recent turns of the conversation as messages.

    The model itself remembers nothing between calls. A follow-up like "same
    for Koramangala" only means something if the earlier question and the SQL
    that answered it are put back in front of it, which is what this does.
    Each turn costs tokens, so only the last few are replayed.
    """
    messages = []
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        question = (turn.get("question") or "").strip()
        sql = (turn.get("sql") or "").strip()
        if not question or not sql:
            continue
        messages.append(HumanMessage(content=question))
        # Presented as the model's own earlier reply, which is exactly what it
        # was. That is what makes "the same query, but..." resolvable.
        messages.append(AIMessage(content=sql))
    return messages


def generate_sql(question: str, history: list[dict] | None = None) -> str:
    """
    Asks the model for a query and returns it only if it passes every check.

    Raises CannotAnswerError if the question is out of scope, or
    UnsafeQueryError if the generated SQL breaks a safety rule.
    """
    settings = get_settings()

    messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(schema=get_schema_description())),
        *build_history_messages(history),
        HumanMessage(content=question.strip()),
    ]

    response = get_llm().invoke(messages)
    raw_sql = message_text(response).strip()
    logger.info("model returned: %s", raw_sql.replace("\n", " ")[:200])

    if "CANNOT_ANSWER" in raw_sql.upper():
        raise CannotAnswerError(extract_refusal_reason(raw_sql))

    # Reasoning-style models sometimes narrate before answering. Keep only the
    # part from the first SELECT or WITH onwards.

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
