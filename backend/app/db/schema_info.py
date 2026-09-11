"""
schema_info.py
--------------
The description of the database that gets handed to the AI with every question.

This text is the single biggest lever on how good the generated SQL is. The
model cannot see your database. All it knows is what is written here, so the
notes about NULL ratings and the de-duplication matter as much as the column
names themselves.
"""

SCHEMA_DESCRIPTION = """
DATABASE: foodiequery  (MySQL 8.4)
Zomato restaurant data for Bangalore, India. Prices are in Indian Rupees.

TABLES
------
restaurants                 one row per real restaurant (12,464 rows)
  restaurant_id   INT        primary key
  name            VARCHAR    restaurant name
  address         VARCHAR    street address
  location_id     INT        -> locations.location_id
  cost_for_two    INT        approximate cost for two people, in rupees. NULL if unknown.
  rating          DECIMAL    0.0 to 5.0. NULL for new or unrated restaurants.
  votes           INT        how many people rated it. 0 is a real value, never NULL.
  online_order    BOOLEAN    accepts online orders (1 = yes)
  book_table      BOOLEAN    accepts table bookings (1 = yes)
  dish_liked      VARCHAR    comma separated popular dishes, often NULL

locations                   93 Bangalore neighbourhoods
  location_id     INT        primary key
  name            VARCHAR    e.g. 'Koramangala 5th Block', 'BTM', 'Whitefield', 'Indiranagar'

cuisines                    107 cuisines
  cuisine_id      INT        primary key
  name            VARCHAR    e.g. 'North Indian', 'Chinese', 'South Indian', 'Cafe', 'Biryani'

restaurant_cuisines         links restaurants to cuisines (many-to-many)
  restaurant_id   INT        -> restaurants.restaurant_id
  cuisine_id      INT        -> cuisines.cuisine_id

restaurant_types            25 restaurant formats
  type_id         INT        primary key
  name            VARCHAR    e.g. 'Casual Dining', 'Quick Bites', 'Cafe', 'Fine Dining', 'Pub', 'Bakery'

restaurant_type_map         links restaurants to formats (many-to-many)
  restaurant_id   INT        -> restaurants.restaurant_id
  type_id         INT        -> restaurant_types.type_id

restaurant_listings         which Zomato browse pages a restaurant appeared on
  restaurant_id   INT        -> restaurants.restaurant_id
  listed_type     VARCHAR    exactly one of: Buffet, Cafes, Delivery, Desserts,
                             Dine-out, Drinks & nightlife, Pubs and bars
  listed_city     VARCHAR    the Zomato city page. NOT the real neighbourhood.

VIEW
----
v_restaurants_full          every restaurant with the joins already done.
  restaurant_id, name, address, location, cost_for_two, rating, votes,
  online_order, book_table, dish_liked,
  cuisines          comma separated text, e.g. 'Chinese, North Indian'
  restaurant_types  comma separated text, e.g. 'Casual Dining'

  Use this view for simple questions. Use the base tables with JOINs when you
  need to filter or group by a single cuisine or type, because searching
  inside the comma separated text is slow and unreliable.

RULES YOU MUST FOLLOW
---------------------
1. Only ever write a SELECT. Never INSERT, UPDATE, DELETE, DROP or ALTER.
2. Always add "WHERE rating IS NOT NULL" when averaging, ranking or filtering
   by rating. 3,011 restaurants have no rating and would otherwise be counted
   as if they were zero-star.
3. When ranking areas or cuisines by average rating, add a HAVING clause with
   a minimum count, usually "HAVING COUNT(*) >= 30". Without it a single
   restaurant with one five-star vote wins.
4. For "best" or "top rated" lists of individual restaurants, also require a
   reasonable number of votes, for example "AND votes >= 100", so a 4.9 from
   three people does not beat a 4.6 from four thousand.
5. Neighbourhood names are inconsistent across blocks. Prefer
   "WHERE l.name LIKE 'Koramangala%'" over an exact match, so all of
   Koramangala's blocks are included.
6. Match cuisine and type names case-insensitively with LIKE when the user's
   wording may not match exactly.
7. Always end with a LIMIT. Use LIMIT 10 unless the question implies more.
8. Use clear column aliases, because the results are shown directly to a
   person. Write "AS avg_rating", not "AS a".
9. Round averages: ROUND(AVG(rating), 2) and ROUND(AVG(cost_for_two)).
10. cost_for_two is the cost for TWO people. If the user asks about the cost
    per person, divide by 2.
"""


def get_schema_description() -> str:
    """Returns the schema text handed to the model with each question."""
    return SCHEMA_DESCRIPTION.strip()
