"""
load_data.py
------------
Builds the MySQL database and loads the cleaned CSV files into it.

Run it with:      python scripts/load_data.py

What it does, in order:
  1. reads your database password from the .env file
  2. runs sql/01_create_schema.sql to create the empty tables
  3. fills the small lookup tables (locations, cuisines, restaurant_types)
  4. fills restaurants, swapping the location text for its new ID number
  5. fills the two many-to-many link tables and the listings table
  6. prints a verification report so you can see it worked

Safe to run as many times as you like. The schema file drops and rebuilds the
tables each time, so you always end up with a clean load rather than duplicates.
"""

import os
import re
import sys
from pathlib import Path

import pandas as pd
import mysql.connector
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CLEANED_DIR = ROOT / "data" / "cleaned"
SCHEMA_FILE = ROOT / "sql" / "01_create_schema.sql"

# Load the .env file sitting in the project root. Without the explicit path,
# python-dotenv searches from this script's folder and can miss it.
load_dotenv(ROOT / ".env")

# How many rows to send to MySQL at a time. Sending one row per round trip
# would take minutes; sending them in batches of 2,000 takes seconds.
BATCH_SIZE = 2000


def get_connection(with_database=True):
    """
    Opens a connection to MySQL using the settings in .env.

    with_database=False is used for the very first connection, because the
    'foodiequery' database does not exist yet and asking for it would fail.
    """
    settings = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD"),
        "charset": "utf8mb4",
    }
    if with_database:
        settings["database"] = os.getenv("DB_NAME", "foodiequery")
    return mysql.connector.connect(**settings)


def split_sql_statements(sql_text):
    """
    Splits a .sql file into individual statements.

    MySQL's Python driver runs one statement per call, but our schema file
    holds about a dozen. We strip the -- comments first so that a semicolon
    inside a comment cannot fool the split.
    """
    without_comments = re.sub(r"--[^\n]*", "", sql_text)
    statements = [s.strip() for s in without_comments.split(";")]
    return [s for s in statements if s]


def run_schema():
    """Creates the database and all the empty tables."""
    print("Creating database and tables ...")
    sql_text = SCHEMA_FILE.read_text(encoding="utf-8")

    connection = get_connection(with_database=False)
    cursor = connection.cursor()
    for statement in split_sql_statements(sql_text):
        cursor.execute(statement)
    connection.commit()
    cursor.close()
    connection.close()
    print("  schema ready")


def insert_many(cursor, sql, rows):
    """Sends rows to MySQL in batches instead of one at a time."""
    for start in range(0, len(rows), BATCH_SIZE):
        cursor.executemany(sql, rows[start:start + BATCH_SIZE])


def to_none(value):
    """
    pandas uses NaN for a missing number, but MySQL wants None (which it
    stores as NULL). Without this, a missing rating would land in the
    database as the text 'nan'.
    """
    return None if pd.isna(value) else value


def load_lookup(cursor, table, id_column, values):
    """
    Fills one of the small reference tables, then hands back a dictionary
    mapping each name to its new ID, e.g. {'Koramangala 5th Block': 42}.
    We need that mapping to fill in the foreign keys on the other tables.
    """
    rows = [(v,) for v in sorted(values)]
    insert_many(cursor, f"INSERT INTO {table} (name) VALUES (%s)", rows)
    cursor.execute(f"SELECT name, {id_column} FROM {table}")
    return {name: row_id for name, row_id in cursor.fetchall()}


def main():
    # --- check the cleaned files exist before touching the database --------
    required = [
        "restaurants.csv", "restaurant_cuisines.csv",
        "restaurant_types.csv", "restaurant_listings.csv",
    ]
    missing = [f for f in required if not (CLEANED_DIR / f).exists()]
    if missing:
        sys.exit(f"Missing cleaned files: {missing}\nRun data_cleaning.py first.")

    if not os.getenv("DB_PASSWORD"):
        sys.exit("DB_PASSWORD is not set in your .env file.")

    run_schema()

    print("Reading cleaned CSV files ...")
    restaurants = pd.read_csv(CLEANED_DIR / "restaurants.csv")
    cuisines_df = pd.read_csv(CLEANED_DIR / "restaurant_cuisines.csv")
    types_df = pd.read_csv(CLEANED_DIR / "restaurant_types.csv")
    listings_df = pd.read_csv(CLEANED_DIR / "restaurant_listings.csv")

    connection = get_connection()
    cursor = connection.cursor()

    # --- Step 1: the three lookup tables -----------------------------------
    print("Loading lookup tables ...")
    location_ids = load_lookup(
        cursor, "locations", "location_id",
        restaurants["location"].dropna().unique(),
    )
    cuisine_ids = load_lookup(
        cursor, "cuisines", "cuisine_id",
        cuisines_df["cuisine"].dropna().unique(),
    )
    type_ids = load_lookup(
        cursor, "restaurant_types", "type_id",
        types_df["rest_type"].dropna().unique(),
    )
    print(f"  locations {len(location_ids)} | cuisines {len(cuisine_ids)}"
          f" | types {len(type_ids)}")

    # --- Step 2: the restaurants themselves --------------------------------
    print("Loading restaurants ...")
    restaurant_rows = [
        (
            int(row.restaurant_id),
            row.name,
            row.address,
            location_ids.get(row.location),      # text swapped for its ID
            to_none(row.cost_for_two),
            to_none(row.rating),
            int(row.votes),
            bool(row.online_order),
            bool(row.book_table),
            to_none(row.dish_liked),
        )
        # itertuples walks the rows far faster than iterrows.
        for row in restaurants.itertuples(index=False)
    ]
    insert_many(cursor, """
        INSERT INTO restaurants
            (restaurant_id, name, address, location_id, cost_for_two,
             rating, votes, online_order, book_table, dish_liked)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, restaurant_rows)
    print(f"  {len(restaurant_rows):,} restaurants")

    # --- Step 3: the link tables -------------------------------------------
    print("Loading link tables ...")
    cuisine_links = [
        (int(r.restaurant_id), cuisine_ids[r.cuisine])
        for r in cuisines_df.itertuples(index=False)
        if r.cuisine in cuisine_ids
    ]
    insert_many(cursor,
                "INSERT INTO restaurant_cuisines (restaurant_id, cuisine_id)"
                " VALUES (%s, %s)", cuisine_links)

    type_links = [
        (int(r.restaurant_id), type_ids[r.rest_type])
        for r in types_df.itertuples(index=False)
        if r.rest_type in type_ids
    ]
    insert_many(cursor,
                "INSERT INTO restaurant_type_map (restaurant_id, type_id)"
                " VALUES (%s, %s)", type_links)

    listing_rows = [
        (int(r.restaurant_id), r.listed_type, r.listed_city)
        for r in listings_df.itertuples(index=False)
    ]
    insert_many(cursor,
                "INSERT INTO restaurant_listings"
                " (restaurant_id, listed_type, listed_city)"
                " VALUES (%s, %s, %s)", listing_rows)
    print(f"  cuisine links {len(cuisine_links):,}"
          f" | type links {len(type_links):,}"
          f" | listings {len(listing_rows):,}")

    # commit makes everything permanent. Until this line, MySQL could still
    # roll the whole load back as if it never happened.
    connection.commit()

    # --- Step 4: verify ----------------------------------------------------
    print("\nVerification:")
    checks = [
        ("locations",           "SELECT COUNT(*) FROM locations"),
        ("cuisines",            "SELECT COUNT(*) FROM cuisines"),
        ("restaurant_types",    "SELECT COUNT(*) FROM restaurant_types"),
        ("restaurants",         "SELECT COUNT(*) FROM restaurants"),
        ("restaurant_cuisines", "SELECT COUNT(*) FROM restaurant_cuisines"),
        ("restaurant_type_map", "SELECT COUNT(*) FROM restaurant_type_map"),
        ("restaurant_listings", "SELECT COUNT(*) FROM restaurant_listings"),
    ]
    for label, query in checks:
        cursor.execute(query)
        print(f"  {label:<22} {cursor.fetchone()[0]:>8,} rows")

    # An orphan is a link row pointing at a restaurant that does not exist.
    # The foreign keys should make this impossible, so it must come back 0.
    cursor.execute("""
        SELECT COUNT(*) FROM restaurant_cuisines rc
        LEFT JOIN restaurants r ON r.restaurant_id = rc.restaurant_id
        WHERE r.restaurant_id IS NULL
    """)
    print(f"  orphaned cuisine links {cursor.fetchone()[0]} (must be 0)")

    cursor.execute("""
        SELECT l.name, COUNT(*) AS restaurants
        FROM restaurants r
        JOIN locations l ON l.location_id = r.location_id
        GROUP BY l.name
        ORDER BY restaurants DESC
        LIMIT 5
    """)
    print("\n  Top 5 areas by restaurant count:")
    for name, count in cursor.fetchall():
        print(f"    {name:<26} {count:>5}")

    cursor.execute("SELECT COUNT(*) FROM v_restaurants_full")
    print(f"\n  view v_restaurants_full returns {cursor.fetchone()[0]:,} rows")

    cursor.close()
    connection.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
