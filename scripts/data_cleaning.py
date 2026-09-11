"""
data_cleaning.py
----------------
Turns the raw Kaggle file (data/raw/zomato.csv) into clean, tidy tables
that are ready to load into MySQL.

Run it with:      python scripts/data_cleaning.py

It NEVER modifies the raw file. It only reads it and writes new files
into data/cleaned/. If you mess something up, just run it again.

It produces four files:
  restaurants.csv          one row per real restaurant
  restaurant_cuisines.csv  restaurant_id -> cuisine   (many rows per restaurant)
  restaurant_types.csv     restaurant_id -> rest_type (many rows per restaurant)
  restaurant_listings.csv  restaurant_id -> the Zomato browse category + city page
"""

from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Paths. Path(__file__).parent.parent means "the folder above this script",
# i.e. the project root. Building paths this way means the script works no
# matter which folder you run it from.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "zomato.csv"
OUT_DIR = ROOT / "data" / "cleaned"

# Columns we actually want. Everything else (url, phone, reviews_list,
# menu_item) is dropped simply by not listing it here. Skipping reviews_list
# is what takes this file from 548 MB down to something that loads in seconds.
KEEP_COLUMNS = [
    "name", "address", "location", "rate", "votes",
    "online_order", "book_table", "rest_type", "cuisines", "dish_liked",
    "approx_cost(for two people)", "listed_in(type)", "listed_in(city)",
]

# Short, SQL-friendly names. Column names like "approx_cost(for two people)"
# are painful to type in SQL because of the brackets and spaces.
RENAME_MAP = {
    "approx_cost(for two people)": "cost_for_two",
    "listed_in(type)": "listed_type",
    "listed_in(city)": "listed_city",
    "rate": "rating",
}


def fix_mojibake(text):
    """
    Repairs text that was encoded and decoded wrongly, several times over.
    In the raw file the word "Cafe" with an accent looks like garbage
    characters. The trick: re-encode the damaged text back to the bytes it
    came from (latin-1) and decode those bytes correctly (utf-8). This file
    was damaged about four times over, so we repeat until it stops changing.
    """
    if not isinstance(text, str):
        return text

    # Some names in this file were damaged six or seven times over, so we
    # loop generously. The loop exits early as soon as the text stops changing.
    for _ in range(12):
        repaired = None
        # latin-1 handles most of it. cp1252 is the fallback for names that
        # also contain a curly apostrophe, which latin-1 cannot encode and
        # which would otherwise abort the repair halfway through.
        for encoding in ("latin-1", "cp1252"):
            try:
                repaired = text.encode(encoding).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        if repaired is None or repaired == text:
            break          # cannot repair further, keep what we have
        text = repaired

    # Leftover invisible control characters are Windows smart quotes and
    # dashes that lost their identity along the way. Translate them back.
    if any(0x80 <= ord(ch) <= 0x9F for ch in text):
        try:
            text = text.encode("latin-1").decode("cp1252")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def clean_rating(value):
    """
    "rate" arrives as text like "4.1/5". We want the number 4.1.

    Special cases in this dataset:
      "NEW" -> a brand new restaurant with no rating yet
      "-"   -> missing
      blank -> missing
    All three become None, which becomes NULL in MySQL. That is correct:
    a missing rating is NOT the same as a rating of zero, and storing 0
    would drag down every average you calculate later.
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value in ("NEW", "-", ""):
        return None
    value = value.split("/")[0]        # "4.1/5" -> "4.1"
    try:
        return float(value)
    except ValueError:
        return None


def clean_cost(value):
    """
    "approx_cost(for two people)" arrives as text like "800" or "1,200".
    The comma is a thousands separator and makes int("1,200") crash,
    so we strip it out before converting.
    """
    if not isinstance(value, str):
        return None
    value = value.replace(",", "").strip()
    try:
        return int(float(value))
    except ValueError:
        return None


def yes_no_to_bool(value):
    """Yes/No text becomes True/False, which MySQL stores as 1/0."""
    return str(value).strip().lower() == "yes"


def tidy_text(value):
    """Trims stray spaces and collapses double spaces. Leaves casing alone."""
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned if cleaned else None


def explode_list_column(df, column, new_name):
    """
    Turns one comma-packed cell into several rows.

    Before:  id 1 | "North Indian, Chinese"
    After:   id 1 | "North Indian"
             id 1 | "Chinese"

    This shape is what a relational database wants. It lets you ask
    "show me every Chinese restaurant" with a simple WHERE clause, instead
    of hunting for text hidden inside a longer string.
    """
    out = (
        df[["restaurant_id", column]]
        .dropna(subset=[column])
        .assign(**{column: lambda d: d[column].str.split(",")})
        .explode(column)
    )
    out[column] = out[column].map(tidy_text)
    out = out.dropna(subset=[column])
    out = out.rename(columns={column: new_name})
    # A restaurant listed under "Cafe" twice should only appear once.
    return out.drop_duplicates().sort_values(["restaurant_id", new_name])


def main():
    print(f"Reading {RAW_FILE.name} ...")
    df = pd.read_csv(RAW_FILE, usecols=KEEP_COLUMNS)
    df = df.rename(columns=RENAME_MAP)
    print(f"  raw rows: {len(df):,}")

    # --- Step 1: clean each column individually -----------------------------
    print("Cleaning columns ...")
    df["name"] = df["name"].map(fix_mojibake).map(tidy_text)
    df["address"] = df["address"].map(fix_mojibake).map(tidy_text)
    df["location"] = df["location"].map(tidy_text)
    df["rating"] = df["rating"].map(clean_rating)
    # "Int64" with a capital I is pandas' integer type that allows blanks.
    # Plain int cannot hold a missing value, and plain float would write
    # "800.0" into the CSV instead of "800".
    df["cost_for_two"] = df["cost_for_two"].map(clean_cost).astype("Int64")
    df["online_order"] = df["online_order"].map(yes_no_to_bool)
    df["book_table"] = df["book_table"].map(yes_no_to_bool)
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce").fillna(0).astype(int)

    # A row with no name or no address is useless to us, drop it.
    df = df.dropna(subset=["name", "address"])

    # --- Step 2: collapse duplicate listings into real restaurants ----------
    # The raw file repeats each restaurant once per browse category, so
    # 51,717 rows are really about 12,500 restaurants. We sort by votes
    # descending first, so that when we keep one row per restaurant we keep
    # the most-reviewed (and usually most complete) version of it.
    print("Collapsing duplicate listings ...")
    df = df.sort_values("votes", ascending=False)
    restaurants = df.drop_duplicates(subset=["name", "address"], keep="first").copy()

    # Give every restaurant a stable ID number, 1, 2, 3 ...
    # This becomes the PRIMARY KEY in MySQL: the one column that uniquely
    # identifies a row, and that other tables point at.
    restaurants = restaurants.sort_values(["name", "address"]).reset_index(drop=True)
    restaurants["restaurant_id"] = range(1, len(restaurants) + 1)
    print(f"  unique restaurants: {len(restaurants):,}")

    # Attach that new ID back onto every original row, so the cuisine and
    # listing tables below know which restaurant they belong to.
    id_lookup = restaurants[["name", "address", "restaurant_id"]]
    df = df.merge(id_lookup, on=["name", "address"], how="left")

    # --- Step 3: build the many-to-many tables ------------------------------
    print("Building cuisine / type / listing tables ...")
    cuisines = explode_list_column(df, "cuisines", "cuisine")
    rest_types = explode_list_column(df, "rest_type", "rest_type")

    listings = (
        df[["restaurant_id", "listed_type", "listed_city"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["restaurant_id", "listed_type"])
    )

    # --- Step 4: final restaurant table -------------------------------------
    restaurants_out = restaurants[[
        "restaurant_id", "name", "address", "location",
        "cost_for_two", "rating", "votes",
        "online_order", "book_table", "dish_liked",
    ]]

    # --- Step 5: write everything out ---------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "restaurants.csv": restaurants_out,
        "restaurant_cuisines.csv": cuisines,
        "restaurant_types.csv": rest_types,
        "restaurant_listings.csv": listings,
    }
    print("\nWriting cleaned files:")
    for filename, table in outputs.items():
        path = OUT_DIR / filename
        # utf-8-sig so Excel opens accented names correctly if you peek at them
        table.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  {filename:<28} {len(table):>7,} rows")

    # --- Step 6: a quick sanity report --------------------------------------
    print("\nSanity check:")
    print(f"  restaurants with a rating : {restaurants_out['rating'].notna().sum():,}"
          f" of {len(restaurants_out):,}")
    print(f"  restaurants with a cost   : {restaurants_out['cost_for_two'].notna().sum():,}"
          f" of {len(restaurants_out):,}")
    print(f"  distinct cuisines         : {cuisines['cuisine'].nunique():,}")
    print(f"  distinct restaurant types : {rest_types['rest_type'].nunique():,}")
    print(f"  distinct locations        : {restaurants_out['location'].nunique():,}")
    print("\nDone.")


if __name__ == "__main__":
    main()
