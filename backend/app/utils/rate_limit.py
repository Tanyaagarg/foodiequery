"""
rate_limit.py
-------------
Caps how many questions one visitor can ask per minute.

Why it matters here: every question costs two calls to Groq's free tier. A
single person hammering refresh, or a bot finding the URL, would burn through
the daily allowance in minutes and take the app down for everyone.

The limiter identifies visitors by IP address and keeps the counts in memory,
which is fine for one server. A multi-server deployment would point it at
Redis instead.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
)

# Read once at import. Changing the limit means restarting the server, which
# is the normal way to change any setting in this app.
QUERY_RATE_LIMIT = get_settings().rate_limit
