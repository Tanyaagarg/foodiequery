"""
sql_guard.py
------------
The safety gate. Every query the AI writes passes through here before it is
allowed anywhere near the database.

This is the most important file in the backend. An AI that writes SQL is,
by definition, a stranger typing commands into your database. The rule is
simple: reading is allowed, everything else is refused.

Three layers protect the data, and this is only the first:
  1. this file, which refuses anything that is not a plain SELECT
  2. a MySQL account that has been granted SELECT and nothing else
  3. a row limit glued onto every query so nothing can dump the whole table
"""

import re

# Anything that changes data, changes the database structure, changes
# permissions, reads files, or stalls the server. Matched as whole words, so
# a restaurant named "Update Cafe" in a WHERE clause will not trip the filter.
FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "replace", "rename", "grant", "revoke", "commit", "rollback",
    "savepoint", "lock", "unlock", "call", "execute", "prepare", "handler",
    "load_file", "outfile", "dumpfile", "infile", "sleep", "benchmark",
    "into", "set", "use", "shutdown", "kill", "flush", "reset",
]

# Tables holding server internals and user accounts. Off limits entirely.
FORBIDDEN_TABLES = [
    "information_schema", "mysql", "performance_schema", "sys",
]


class UnsafeQueryError(Exception):
    """Raised when a generated query fails any safety check."""


def strip_markdown_fences(text: str) -> str:
    """
    Language models like to wrap code in ```sql ... ``` fences even when told
    not to. This pulls the SQL back out of them.
    """
    text = text.strip()
    fence = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    return text.strip()


def strip_sql_comments(sql: str) -> str:
    """
    Removes -- line comments and /* block comments */.

    Not for tidiness. A comment is a classic way to smuggle a second command
    past a naive check, so we look at the query with all comments removed.
    """
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def strip_string_literals(sql: str) -> str:
    """
    Blanks out anything inside quotes.

    A restaurant called "Set Menu Delhi" contains the word 'set'. We must not
    reject a perfectly good query because of a value the user searched for,
    so keyword checks run against a copy with the quoted text removed.
    """
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
    sql = re.sub(r'"(?:[^"]|"")*"', '""', sql)
    return sql


def validate_sql(raw_sql: str) -> str:
    """
    Checks a generated query and returns a cleaned, safe version of it.

    Raises UnsafeQueryError with a plain-English reason if anything is wrong.
    """
    sql = strip_markdown_fences(raw_sql)
    if not sql:
        raise UnsafeQueryError("The model returned an empty query.")

    # MySQL has a trap called an executable comment. Text inside /*! ... */
    # looks like a comment to every other database and to any code that strips
    # comments, but MySQL RUNS it. Refuse these outright rather than trying to
    # parse them, because this is exactly how a filter gets walked around.
    if re.search(r"/\*!", sql):
        raise UnsafeQueryError(
            "MySQL executable comments (/*! ... */) are not allowed."
        )

    # Drop a single trailing semicolon. Anything beyond that means the model
    # tried to send more than one command, which we never allow.
    sql = sql.rstrip().rstrip(";").rstrip()

    inspectable = strip_string_literals(strip_sql_comments(sql))

    if ";" in inspectable:
        raise UnsafeQueryError(
            "Only one statement is allowed, and this query contains several."
        )

    # Must be a read. WITH is allowed because a CTE still ends in a SELECT.
    first_word = re.match(r"^\s*(\w+)", inspectable)
    if not first_word or first_word.group(1).lower() not in ("select", "with"):
        raise UnsafeQueryError(
            "Only SELECT queries are allowed. This one starts with "
            f"'{first_word.group(1) if first_word else '?'}'."
        )

    if first_word.group(1).lower() == "with" and not re.search(
        r"\bselect\b", inspectable, re.IGNORECASE
    ):
        raise UnsafeQueryError("A WITH block must end in a SELECT.")

    lowered = inspectable.lower()

    for keyword in FORBIDDEN_KEYWORDS:
        # \b is a word boundary, so 'set' matches the command SET but not the
        # column name 'offset' or the function 'GROUP_CONCAT ... SEPARATOR'.
        if re.search(rf"\b{keyword}\b", lowered):
            raise UnsafeQueryError(
                f"The keyword '{keyword.upper()}' is not allowed. "
                "This API can only read data."
            )

    for table in FORBIDDEN_TABLES:
        if re.search(rf"\b{table}\b", lowered):
            raise UnsafeQueryError(
                f"Querying '{table}' is not allowed."
            )

    return sql


def enforce_row_limit(sql: str, max_rows: int) -> str:
    """
    Makes sure the query cannot return more rows than we allow.

    If the model already wrote a LIMIT we respect it, unless it is bigger than
    our cap, in which case we shrink it. If it wrote none, we add one.
    """
    match = re.search(r"\blimit\s+(\d+)\s*$", sql, re.IGNORECASE)
    if match:
        requested = int(match.group(1))
        if requested <= max_rows:
            return sql
        return sql[: match.start()] + f"LIMIT {max_rows}"

    # Some other shape of LIMIT, such as "LIMIT 5, 10" or one inside a
    # subquery. Appending another would be a syntax error, so leave it be.
    # The database layer stops reading after max_rows anyway.
    if re.search(r"\blimit\b", sql, re.IGNORECASE):
        return sql

    return f"{sql}\nLIMIT {max_rows}"
