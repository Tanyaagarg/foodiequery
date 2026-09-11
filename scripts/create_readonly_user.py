"""
create_readonly_user.py
-----------------------
Creates a MySQL account that is allowed to read the foodiequery database and
nothing else, then saves its credentials into your .env file.

Run it once:      python scripts/create_readonly_user.py

Why bother, when sql_guard.py already blocks dangerous queries?

Because one layer of defence is one bug away from no defence. sql_guard is
code we wrote, and code we wrote can be wrong. This account is enforced by
MySQL itself. Even a perfectly formed DROP TABLE sent by the API would be
refused, because the account has never been granted permission to do it.

Security people call this defence in depth. It is also a good thing to be
able to explain in an interview.
"""

import os
import secrets
import string
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

load_dotenv(ENV_FILE)

RO_USER = "foodiequery_ro"
# MySQL treats a TCP connection to 127.0.0.1 and one to localhost as different
# hosts, so the account is created for both. Neither can be reached from
# another machine.
RO_HOSTS = ["localhost", "127.0.0.1"]


def generate_password(length: int = 24) -> str:
    """
    Makes a strong random password.

    secrets, not random: the random module is predictable by design and must
    never be used for anything security related.
    """
    alphabet = string.ascii_letters + string.digits + "!@#%^*-_="
    return "".join(secrets.choice(alphabet) for _ in range(length))


def write_env_value(key: str, value: str) -> None:
    """Adds or replaces one KEY=value line in .env, leaving the rest alone."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# --- read-only database account used by the API ---")
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    root_password = os.getenv("DB_PASSWORD")
    if not root_password:
        sys.exit("DB_PASSWORD is not set in .env")

    database = os.getenv("DB_NAME", "foodiequery")

    # Reuse the existing password if this script has been run before, so the
    # .env file and the MySQL account cannot drift apart.
    password = os.getenv("DB_RO_PASSWORD") or generate_password()

    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=root_password,
    )
    cursor = connection.cursor()

    for host in RO_HOSTS:
        account = f"'{RO_USER}'@'{host}'"

        # CREATE IF NOT EXISTS then ALTER, so re-running this script resets the
        # password rather than failing.
        cursor.execute(f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY %s",
                       (password,))
        cursor.execute(f"ALTER USER {account} IDENTIFIED BY %s", (password,))

        # The whole point of the script. SELECT, and nothing else.
        cursor.execute(f"GRANT SELECT ON `{database}`.* TO {account}")

        # Cap how much of the server one account can consume, in case a query
        # slips through that is expensive rather than dangerous.
        cursor.execute(
            f"ALTER USER {account} WITH MAX_QUERIES_PER_HOUR 2000 "
            "MAX_CONNECTIONS_PER_HOUR 500 MAX_USER_CONNECTIONS 10"
        )
        print(f"  granted SELECT on {database}.* to {account}")

    cursor.execute("FLUSH PRIVILEGES")
    connection.commit()

    # --- prove it is actually restricted -----------------------------------
    cursor.execute(f"SHOW GRANTS FOR '{RO_USER}'@'localhost'")
    print("\nGrants now held by the account:")
    for (grant,) in cursor.fetchall():
        print(f"  {grant}")

    cursor.close()
    connection.close()

    write_env_value("DB_RO_USER", RO_USER)
    write_env_value("DB_RO_PASSWORD", password)
    print(f"\nSaved DB_RO_USER and DB_RO_PASSWORD to .env")

    # --- and confirm that writing really is refused -------------------------
    test = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=RO_USER,
        password=password,
        database=database,
    )
    test_cursor = test.cursor()

    test_cursor.execute("SELECT COUNT(*) FROM restaurants")
    print(f"\nRead test  : OK, sees {test_cursor.fetchone()[0]:,} restaurants")

    try:
        test_cursor.execute("DELETE FROM restaurants WHERE restaurant_id = 999999")
        print("Write test : FAILED, the account was able to delete. Investigate.")
    except mysql.connector.Error as exc:
        print(f"Write test : correctly refused ({exc.errno} access denied)")

    test_cursor.close()
    test.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
