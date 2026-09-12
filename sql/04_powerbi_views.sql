-- ============================================================================
-- FoodieQuery : views for Power BI
-- ============================================================================
-- Run this once in MySQL Workbench before connecting Power BI.
--
-- Why separate views instead of pointing Power BI at the raw tables?
--
--   1. Fewer tables to wire together. Power BI would otherwise need seven
--      tables and six relationships. These four need three.
--   2. The ID columns are already swapped for readable names, so a chart
--      legend says "Koramangala 5th Block" instead of 47.
--   3. The grouping bands (price band, rating band) are computed here once.
--      Doing it in SQL means every chart uses the same definition of
--      "expensive", and you do not have to learn DAX to get them.
--
-- A view stores no data. It is a saved query that behaves like a table, so it
-- always reflects whatever is in the real tables underneath.
-- ============================================================================

USE foodiequery;


-- ---------------------------------------------------------------------------
-- vw_bi_restaurants : the main table for the dashboard, one row per restaurant
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_bi_restaurants;
CREATE VIEW vw_bi_restaurants AS
SELECT
    r.restaurant_id,
    r.name                              AS restaurant,
    r.address,
    COALESCE(l.name, 'Unknown')         AS area,
    r.cost_for_two,
    r.rating,
    r.votes,
    r.dish_liked,

    -- Yes/No rather than 1/0. Power BI shows the raw value in slicers and
    -- legends, and "Yes" is readable where "1" needs explaining.
    CASE WHEN r.online_order THEN 'Yes' ELSE 'No' END  AS online_order,
    CASE WHEN r.book_table   THEN 'Yes' ELSE 'No' END  AS book_table,

    -- Price bands. The number prefix forces the right order in a chart,
    -- which would otherwise sort these alphabetically and put 1000 first.
    CASE
        WHEN r.cost_for_two IS NULL THEN '6. Unknown'
        WHEN r.cost_for_two <  300  THEN '1. Under 300'
        WHEN r.cost_for_two <  600  THEN '2. 300 to 599'
        WHEN r.cost_for_two < 1000  THEN '3. 600 to 999'
        WHEN r.cost_for_two < 1500  THEN '4. 1000 to 1499'
        ELSE                             '5. 1500 and above'
    END                                 AS price_band,

    CASE
        WHEN r.rating IS NULL  THEN '6. Not rated'
        WHEN r.rating >= 4.5   THEN '1. 4.5 and above'
        WHEN r.rating >= 4.0   THEN '2. 4.0 to 4.4'
        WHEN r.rating >= 3.5   THEN '3. 3.5 to 3.9'
        WHEN r.rating >= 3.0   THEN '4. 3.0 to 3.4'
        ELSE                        '5. Below 3.0'
    END                                 AS rating_band,

    CASE
        WHEN r.votes >= 1000 THEN '1. 1000 or more'
        WHEN r.votes >=  500 THEN '2. 500 to 999'
        WHEN r.votes >=  200 THEN '3. 200 to 499'
        WHEN r.votes >=   50 THEN '4. 50 to 199'
        ELSE                      '5. Under 50'
    END                                 AS vote_band,

    -- A simple value-for-money score: rating earned per 1000 rupees spent.
    -- Higher is better value. NULL where either input is missing, so it never
    -- silently invents a score.
    CASE
        WHEN r.rating IS NOT NULL AND r.cost_for_two > 0
        THEN ROUND(r.rating / r.cost_for_two * 1000, 2)
    END                                 AS value_score,

    -- A flag for "this rating can be trusted", used to filter charts.
    CASE WHEN r.votes >= 100 THEN 'Yes' ELSE 'No' END  AS well_reviewed

FROM restaurants r
LEFT JOIN locations l ON l.location_id = r.location_id;


-- ---------------------------------------------------------------------------
-- vw_bi_cuisines : one row per restaurant per cuisine
-- ---------------------------------------------------------------------------
-- A restaurant serving three cuisines appears three times. That is correct
-- and expected: it lets a cuisine slicer filter the main table. It also means
-- you must count restaurants with DISTINCTCOUNT, never COUNT, on this table.
DROP VIEW IF EXISTS vw_bi_cuisines;
CREATE VIEW vw_bi_cuisines AS
SELECT
    rc.restaurant_id,
    c.name AS cuisine
FROM restaurant_cuisines rc
JOIN cuisines c ON c.cuisine_id = rc.cuisine_id;


-- ---------------------------------------------------------------------------
-- vw_bi_types : one row per restaurant per format (Cafe, Pub, Fine Dining...)
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_bi_types;
CREATE VIEW vw_bi_types AS
SELECT
    rm.restaurant_id,
    rt.name AS restaurant_type
FROM restaurant_type_map rm
JOIN restaurant_types rt ON rt.type_id = rm.type_id;


-- ---------------------------------------------------------------------------
-- vw_bi_listings : which Zomato browse pages each restaurant appeared under
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_bi_listings;
CREATE VIEW vw_bi_listings AS
SELECT DISTINCT
    restaurant_id,
    listed_type AS browse_category,
    listed_city AS city_page
FROM restaurant_listings;


-- ---------------------------------------------------------------------------
-- Check the views before leaving Workbench
-- ---------------------------------------------------------------------------
SELECT 'vw_bi_restaurants' AS view_name, COUNT(*) AS rows_returned FROM vw_bi_restaurants
UNION ALL SELECT 'vw_bi_cuisines', COUNT(*) FROM vw_bi_cuisines
UNION ALL SELECT 'vw_bi_types',    COUNT(*) FROM vw_bi_types
UNION ALL SELECT 'vw_bi_listings', COUNT(*) FROM vw_bi_listings;
-- Expected: 12464, 29269, 14238, 51628
