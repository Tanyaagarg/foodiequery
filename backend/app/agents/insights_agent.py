"""
insights_agent.py
-----------------
Agent 2 of 2. Reads the query results and writes two or three sentences
explaining what they mean.

A table of numbers is not an answer. This is what turns
"Whitefield 885, Electronic City 730" into
"Whitefield leads with 885 restaurants, comfortably ahead of Electronic City."

Note that this agent never touches the database. It only sees rows that have
already been fetched, so there is nothing here that can go wrong with data.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.sql_agent import get_llm, message_text

logger = logging.getLogger(__name__)

# How many rows to show the model. Sending hundreds wastes tokens and time,
# and the headline is almost always in the first handful anyway.
MAX_ROWS_FOR_INSIGHT = 25

SYSTEM_PROMPT = """You are a restaurant data analyst explaining query results \
to a non-technical person.

Write 2 to 3 short sentences in plain English.

Rules:
- Lead with the direct answer to the question.
- The data covers restaurants in BANGALORE ONLY. If the question implies a
  wider area, such as India or "anywhere", say in one short clause that the
  answer covers Bangalore. Never present "they are all in Bangalore" as a
  finding, because every restaurant in the data is.
- Quote the specific numbers that matter. Never invent a number that is not
  in the results.
- If you spot something genuinely interesting, such as a surprising gap or a
  pattern, add one sentence about it. If nothing stands out, stop at the answer.
- Prices are in Indian Rupees. Write them as Rs 450.
- No markdown, no bullet points, no headings. Just sentences.
- Never mention SQL, queries, tables, columns or rows.
- If the results are empty, say plainly that nothing matched, and suggest one
  way to loosen the search.
"""


def generate_insight(question: str, columns: list[str], rows: list[dict]) -> str:
    """
    Turns query results into a short spoken-English summary.

    Never raises. If the model is unavailable, the user still gets their table
    plus a neutral sentence, rather than an error page.
    """
    sample = rows[:MAX_ROWS_FOR_INSIGHT]

    if not rows:
        results_text = "The query returned no rows."
    else:
        results_text = (
            f"Columns: {', '.join(columns)}\n"
            f"Rows returned: {len(rows)}"
            f"{' (showing the first ' + str(len(sample)) + ')' if len(rows) > len(sample) else ''}\n\n"
            # default=str so any leftover Decimal or date does not crash the dump
            f"{json.dumps(sample, indent=2, default=str, ensure_ascii=False)}"
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Question asked:\n{question.strip()}\n\nResults:\n{results_text}"
        ),
    ]

    try:
        # A little randomness here, unlike the SQL agent. Zero temperature
        # makes prose stilted and repetitive, and there is no single correct
        # wording to hit.
        response = get_llm(temperature=0.3).invoke(messages)
        insight = message_text(response).strip()
        return insight or _fallback(len(rows))
    except Exception as exc:                      # noqa: BLE001
        logger.warning("insight generation failed: %s", exc)
        return _fallback(len(rows))


def _fallback(row_count: int) -> str:
    """Used when the model cannot be reached. The table is still shown."""
    if row_count == 0:
        return "Nothing matched that search. Try widening it a little."
    return f"Found {row_count} matching result{'s' if row_count != 1 else ''}."
