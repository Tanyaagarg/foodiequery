-- ============================================================================
-- FoodieQuery : verification checks
-- ============================================================================
-- Run these in MySQL Workbench AFTER load_data.py has finished.
-- Highlight one query and press Ctrl+Enter to run just that one.
-- ============================================================================

USE foodiequery;


-- ---------------------------------------------------------------------------
-- 1. Are all seven tables there, and is the row count right?
-- ---------------------------------------------------------------------------
SELECT 'locations'            AS table_name, COUNT(*) AS rows_loaded FROM locations
UNION ALL SELECT 'cuisines',            COUNT(*) FROM cuisines
UNION ALL SELECT 'restaurant_types',    COUNT(*) FROM restaurant_types
UNION ALL SELECT 'restaurants',         COUNT(*) FROM restaurants
UNION ALL SELECT 'restaurant_cuisines', COUNT(*) FROM restaurant_cuisines
UNION ALL SELECT 'restaurant_type_map', COUNT(*) FROM restaurant_type_map
UNION ALL SELECT 'restaurant_listings', COUNT(*) FROM restaurant_listings;
-- UNION ALL stacks several small results into one list.
-- Expected: 93, 107, 25, 12464, 29269, 14238, 51628


-- ---------------------------------------------------------------------------
-- 2. Eyeball ten restaurants. Do the values look sane?
-- ---------------------------------------------------------------------------
SELECT restaurant_id, name, cost_for_two, rating, votes, online_order, book_table
FROM restaurants
ORDER BY votes DESC
LIMIT 10;
-- These are the ten most-reviewed restaurants in Bangalore.
-- rating should be a number like 4.4, never text like '4.4/5'.


-- ---------------------------------------------------------------------------
-- 3. Did the missing ratings stay missing instead of turning into zero?
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                   AS total_restaurants,
    COUNT(rating)                              AS have_a_rating,
    SUM(rating IS NULL)                        AS rating_missing,
    SUM(cost_for_two IS NULL)                  AS cost_missing,
    MIN(rating)                                AS lowest_rating,
    MAX(rating)                                AS highest_rating
FROM restaurants;
-- COUNT(column) skips NULLs, while COUNT(*) counts every row. The gap between
-- the two is exactly how much data is missing.
-- Expected: 12464 total, 9453 rated, lowest 1.8, highest 4.9.
-- If lowest_rating came back as 0.0, the cleaning step failed.


-- ---------------------------------------------------------------------------
-- 4. Do the JOINs work? Pull one restaurant apart across all its tables.
-- ---------------------------------------------------------------------------
SELECT
    r.name,
    l.name  AS area,
    r.rating,
    r.cost_for_two,
    c.name  AS cuisine
FROM restaurants r
JOIN locations           l  ON l.location_id   = r.location_id
JOIN restaurant_cuisines rc ON rc.restaurant_id = r.restaurant_id
JOIN cuisines            c  ON c.cuisine_id    = rc.cuisine_id
WHERE r.name = 'Meghana Foods'
ORDER BY l.name, c.name;
-- One row per branch per cuisine. Meghana Foods has several branches and
-- several cuisines each, so you should get a handful of rows back.


-- ---------------------------------------------------------------------------
-- 5. Are there any orphans? Link rows pointing at a restaurant that is gone.
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS orphaned_links
FROM restaurant_cuisines rc
LEFT JOIN restaurants r ON r.restaurant_id = rc.restaurant_id
WHERE r.restaurant_id IS NULL;
-- LEFT JOIN keeps every link row even when no restaurant matches. Those
-- unmatched rows show up as NULL, so this counts them.
-- The foreign keys should make orphans impossible. Expected: 0


-- ---------------------------------------------------------------------------
-- 6. Does the flattened view work?
-- ---------------------------------------------------------------------------
SELECT name, location, rating, cost_for_two, cuisines, restaurant_types
FROM v_restaurants_full
WHERE rating >= 4.5
ORDER BY votes DESC
LIMIT 10;
-- Same data as query 4, but the view has done the joining for you and glued
-- the cuisines into one readable list.


-- ---------------------------------------------------------------------------
-- 7. A real business question, to prove the whole thing hangs together
-- ---------------------------------------------------------------------------
SELECT
    l.name                    AS area,
    COUNT(*)                  AS restaurants,
    ROUND(AVG(r.rating), 2)   AS avg_rating,
    ROUND(AVG(r.cost_for_two)) AS avg_cost_for_two
FROM restaurants r
JOIN locations l ON l.location_id = r.location_id
GROUP BY l.name
HAVING COUNT(*) >= 100
ORDER BY restaurants DESC
LIMIT 10;
-- GROUP BY collapses all restaurants in an area into one summary row.
-- HAVING filters those summary rows. WHERE cannot do this, because WHERE
-- runs before the grouping happens and HAVING runs after.
-- Expected top row: Whitefield, 885 restaurants.
