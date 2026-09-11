-- ============================================================================
-- FoodieQuery : analytical queries
-- ============================================================================
-- 19 queries answering real business questions about Bangalore's restaurant
-- market, grouped into five themes.
--
-- These serve two purposes:
--   1. they are the SQL portion of the portfolio
--   2. they are the test set for the AI agent in Phase 5. If the agent's
--      generated SQL for the same question matches the shape of these, it works.
--
-- Run one at a time: click inside a query and press Ctrl+Enter.
--
-- One rule applies everywhere below: 3,011 of the 12,464 restaurants have no
-- rating, because they are new or nobody rated them. Every rating query
-- therefore says "WHERE rating IS NOT NULL", and most add a minimum-count
-- filter so that one five-star restaurant cannot make a whole area look great.
-- ============================================================================

USE foodiequery;


-- ############################################################################
-- THEME 1 : LOCATION INSIGHTS
-- Where are the restaurants, what do they cost, and where is the good food?
-- ############################################################################

-- ---------------------------------------------------------------------------
-- Q1. Which areas of Bangalore have the most restaurants?
-- Business question: where is the competition densest?
-- ---------------------------------------------------------------------------
SELECT
    l.name                       AS area,
    COUNT(*)                     AS restaurant_count,
    ROUND(AVG(r.rating), 2)      AS avg_rating,
    ROUND(AVG(r.cost_for_two))   AS avg_cost_for_two
FROM restaurants r
JOIN locations l ON l.location_id = r.location_id
GROUP BY l.name
ORDER BY restaurant_count DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q2. Which areas are the most and least expensive to eat in?
-- Business question: where does a meal for two cost the most?
-- Only areas with 50+ restaurants, so a single fine-dining spot in a quiet
-- suburb cannot claim the top slot.
-- ---------------------------------------------------------------------------
SELECT
    l.name                        AS area,
    COUNT(*)                      AS restaurant_count,
    ROUND(AVG(r.cost_for_two))    AS avg_cost_for_two,
    MIN(r.cost_for_two)           AS cheapest,
    MAX(r.cost_for_two)           AS priciest
FROM restaurants r
JOIN locations l ON l.location_id = r.location_id
WHERE r.cost_for_two IS NOT NULL
GROUP BY l.name
HAVING COUNT(*) >= 50
ORDER BY avg_cost_for_two DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q3. Which areas have the best-rated food?
-- Business question: density is not quality. Where is the food actually good?
-- ---------------------------------------------------------------------------
SELECT
    l.name                      AS area,
    COUNT(r.rating)             AS rated_restaurants,
    ROUND(AVG(r.rating), 2)     AS avg_rating,
    ROUND(AVG(r.cost_for_two))  AS avg_cost_for_two
FROM restaurants r
JOIN locations l ON l.location_id = r.location_id
WHERE r.rating IS NOT NULL
GROUP BY l.name
HAVING COUNT(r.rating) >= 50
ORDER BY avg_rating DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q4. Where has online ordering caught on the most?
-- Business question: which neighbourhoods are delivery-first?
-- AVG() on a true/false column gives the proportion that are true, because
-- MySQL stores them as 1 and 0. Multiply by 100 for a percentage.
-- ---------------------------------------------------------------------------
SELECT
    l.name                                     AS area,
    COUNT(*)                                   AS restaurant_count,
    SUM(r.online_order)                        AS accepts_online_orders,
    ROUND(AVG(r.online_order) * 100, 1)        AS pct_online_order
FROM restaurants r
JOIN locations l ON l.location_id = r.location_id
GROUP BY l.name
HAVING COUNT(*) >= 50
ORDER BY pct_online_order DESC
LIMIT 15;


-- ############################################################################
-- THEME 2 : CUISINE INSIGHTS
-- What does Bangalore eat, and what does each kind of food cost?
-- ############################################################################

-- ---------------------------------------------------------------------------
-- Q5. What are the most common cuisines?
-- Business question: which cuisine is the market saturated with?
-- ---------------------------------------------------------------------------
SELECT
    c.name                      AS cuisine,
    COUNT(*)                    AS restaurant_count,
    ROUND(AVG(r.rating), 2)     AS avg_rating,
    ROUND(AVG(r.cost_for_two))  AS avg_cost_for_two
FROM restaurant_cuisines rc
JOIN cuisines    c ON c.cuisine_id   = rc.cuisine_id
JOIN restaurants r ON r.restaurant_id = rc.restaurant_id
GROUP BY c.name
ORDER BY restaurant_count DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q6. Which cuisines are rated highest?
-- Business question: popularity and quality are not the same thing. Which
-- cuisines does Bangalore actually rate well?
-- ---------------------------------------------------------------------------
SELECT
    c.name                      AS cuisine,
    COUNT(r.rating)             AS rated_restaurants,
    ROUND(AVG(r.rating), 2)     AS avg_rating,
    ROUND(AVG(r.cost_for_two))  AS avg_cost_for_two
FROM restaurant_cuisines rc
JOIN cuisines    c ON c.cuisine_id    = rc.cuisine_id
JOIN restaurants r ON r.restaurant_id = rc.restaurant_id
WHERE r.rating IS NOT NULL
GROUP BY c.name
HAVING COUNT(r.rating) >= 50
ORDER BY avg_rating DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q7. Which cuisines are the most expensive?
-- Business question: what does each kind of food cost for two people?
-- ---------------------------------------------------------------------------
SELECT
    c.name                      AS cuisine,
    COUNT(*)                    AS restaurant_count,
    ROUND(AVG(r.cost_for_two))  AS avg_cost_for_two,
    ROUND(AVG(r.rating), 2)     AS avg_rating
FROM restaurant_cuisines rc
JOIN cuisines    c ON c.cuisine_id    = rc.cuisine_id
JOIN restaurants r ON r.restaurant_id = rc.restaurant_id
WHERE r.cost_for_two IS NOT NULL
GROUP BY c.name
HAVING COUNT(*) >= 50
ORDER BY avg_cost_for_two DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Q8. Which cuisines get served together?
-- Business question: what pairings do restaurants bet on?
-- This joins restaurant_cuisines to itself. rc1.cuisine_id < rc2.cuisine_id
-- does two jobs: it stops a cuisine pairing with itself, and it stops the
-- same pair appearing twice as (Chinese, Thai) and (Thai, Chinese).
-- ---------------------------------------------------------------------------
SELECT
    c1.name    AS cuisine_a,
    c2.name    AS cuisine_b,
    COUNT(*)   AS restaurants_serving_both
FROM restaurant_cuisines rc1
JOIN restaurant_cuisines rc2
      ON rc2.restaurant_id = rc1.restaurant_id
     AND rc2.cuisine_id    > rc1.cuisine_id
JOIN cuisines c1 ON c1.cuisine_id = rc1.cuisine_id
JOIN cuisines c2 ON c2.cuisine_id = rc2.cuisine_id
GROUP BY c1.name, c2.name
ORDER BY restaurants_serving_both DESC
LIMIT 15;


-- ############################################################################
-- THEME 3 : RATING PATTERNS
-- What actually correlates with a good rating?
-- ############################################################################

-- ---------------------------------------------------------------------------
-- Q9. Do restaurants that accept online orders rate higher?
-- ---------------------------------------------------------------------------
SELECT
    CASE WHEN online_order THEN 'Accepts online orders'
         ELSE 'No online ordering' END   AS online_ordering,
    COUNT(*)                             AS rated_restaurants,
    ROUND(AVG(rating), 2)                AS avg_rating,
    ROUND(AVG(votes))                    AS avg_votes,
    ROUND(AVG(cost_for_two))             AS avg_cost_for_two
FROM restaurants
WHERE rating IS NOT NULL
GROUP BY online_order;


-- ---------------------------------------------------------------------------
-- Q10. Do restaurants that take table bookings rate higher?
-- ---------------------------------------------------------------------------
SELECT
    CASE WHEN book_table THEN 'Takes table bookings'
         ELSE 'No table booking' END     AS table_booking,
    COUNT(*)                             AS rated_restaurants,
    ROUND(AVG(rating), 2)                AS avg_rating,
    ROUND(AVG(votes))                    AS avg_votes,
    ROUND(AVG(cost_for_two))             AS avg_cost_for_two
FROM restaurants
WHERE rating IS NOT NULL
GROUP BY book_table;


-- ---------------------------------------------------------------------------
-- Q11. Does spending more get you better food?
-- Business question: is price a reliable signal of quality?
-- CASE turns a continuous number into labelled buckets, which is the only
-- way to group by a price range rather than by every distinct price.
-- ---------------------------------------------------------------------------
SELECT
    CASE
        WHEN cost_for_two <  300 THEN 'a. Under 300'
        WHEN cost_for_two <  600 THEN 'b. 300 to 599'
        WHEN cost_for_two < 1000 THEN 'c. 600 to 999'
        WHEN cost_for_two < 1500 THEN 'd. 1000 to 1499'
        ELSE                          'e. 1500 and above'
    END                          AS price_band,
    COUNT(*)                     AS rated_restaurants,
    ROUND(AVG(rating), 2)        AS avg_rating,
    ROUND(AVG(votes))            AS avg_votes
FROM restaurants
WHERE rating IS NOT NULL
  AND cost_for_two IS NOT NULL
GROUP BY price_band
ORDER BY price_band;
-- The a. b. c. prefixes exist only so the bands sort in price order instead
-- of alphabetically.


-- ---------------------------------------------------------------------------
-- Q12. Are heavily reviewed restaurants better, or just busier?
-- Business question: does vote count predict rating?
-- ---------------------------------------------------------------------------
SELECT
    CASE
        WHEN votes <   50 THEN 'a. Under 50 votes'
        WHEN votes <  200 THEN 'b. 50 to 199'
        WHEN votes <  500 THEN 'c. 200 to 499'
        WHEN votes < 1000 THEN 'd. 500 to 999'
        ELSE                   'e. 1000 or more'
    END                        AS popularity_band,
    COUNT(*)                   AS rated_restaurants,
    ROUND(AVG(rating), 2)      AS avg_rating,
    ROUND(AVG(cost_for_two))   AS avg_cost_for_two
FROM restaurants
WHERE rating IS NOT NULL
GROUP BY popularity_band
ORDER BY popularity_band;


-- ############################################################################
-- THEME 4 : BUSINESS QUESTIONS
-- The answers a customer or an investor would actually pay for.
-- ############################################################################

-- ---------------------------------------------------------------------------
-- Q13. Best value for money in Bangalore.
-- Business question: highly rated, genuinely cheap, and enough votes that
-- the rating can be trusted.
-- ---------------------------------------------------------------------------
SELECT
    r.name                                  AS restaurant,
    l.name                                  AS area,
    r.rating,
    r.votes,
    r.cost_for_two,
    ROUND(r.rating / r.cost_for_two * 1000, 2) AS rating_per_1000_spent
FROM restaurants r
JOIN locations l ON l.location_id = r.location_id
WHERE r.rating >= 4.2
  AND r.cost_for_two <= 400
  AND r.votes >= 200
ORDER BY r.rating DESC, r.votes DESC
LIMIT 20;
-- votes >= 200 is the trust filter. A 4.9 from six people means nothing.


-- ---------------------------------------------------------------------------
-- Q14. The premium segment.
-- Business question: who plays at the top of the market, and is the food
-- good enough to justify the price?
-- ---------------------------------------------------------------------------
SELECT
    r.name           AS restaurant,
    l.name           AS area,
    r.cost_for_two,
    r.rating,
    r.votes,
    r.book_table
FROM restaurants r
JOIN locations l ON l.location_id = r.location_id
WHERE r.cost_for_two >= 2000
  AND r.rating IS NOT NULL
ORDER BY r.cost_for_two DESC, r.rating DESC
LIMIT 20;


-- ---------------------------------------------------------------------------
-- Q15. Expensive but disappointing.
-- Business question: which restaurants charge premium prices and fail to
-- deliver? These are the market's weak spots.
-- ---------------------------------------------------------------------------
SELECT
    r.name          AS restaurant,
    l.name          AS area,
    r.cost_for_two,
    r.rating,
    r.votes
FROM restaurants r
JOIN locations l ON l.location_id = r.location_id
WHERE r.cost_for_two >= 1000
  AND r.rating < 3.5
  AND r.votes >= 100
ORDER BY r.cost_for_two DESC
LIMIT 20;


-- ---------------------------------------------------------------------------
-- Q16. The signature cuisine of each major area.
-- Business question: what is each neighbourhood known for?
-- This uses a CTE and a window function, the two most advanced pieces of SQL
-- in this file.
--   A CTE (the WITH block) is a named temporary result you can then query,
--   which keeps a two-stage question readable.
--   ROW_NUMBER() OVER (PARTITION BY area ORDER BY n DESC) numbers the rows
--   1, 2, 3 ... restarting the count for every area. Keeping rn = 1 keeps
--   the single most common cuisine per area.
-- ---------------------------------------------------------------------------
WITH area_cuisine_counts AS (
    SELECT
        l.name                  AS area,
        c.name                  AS cuisine,
        COUNT(*)                AS restaurant_count,
        ROUND(AVG(r.rating), 2) AS avg_rating
    FROM restaurants r
    JOIN locations           l  ON l.location_id   = r.location_id
    JOIN restaurant_cuisines rc ON rc.restaurant_id = r.restaurant_id
    JOIN cuisines            c  ON c.cuisine_id    = rc.cuisine_id
    GROUP BY l.name, c.name
),
ranked AS (
    SELECT
        area, cuisine, restaurant_count, avg_rating,
        ROW_NUMBER() OVER (PARTITION BY area ORDER BY restaurant_count DESC) AS rn,
        SUM(restaurant_count) OVER (PARTITION BY area) AS area_total
    FROM area_cuisine_counts
)
SELECT area, cuisine AS top_cuisine, restaurant_count, avg_rating
FROM ranked
WHERE rn = 1
  AND area_total >= 200
ORDER BY restaurant_count DESC
LIMIT 20;


-- ############################################################################
-- THEME 5 : RESTAURANT FORMAT
-- Cafes, pubs, quick bites, fine dining. Who wins on what?
-- ############################################################################

-- ---------------------------------------------------------------------------
-- Q17. How does each restaurant format perform?
-- Business question: which format is most common, best rated, priciest?
-- ---------------------------------------------------------------------------
SELECT
    rt.name                                AS restaurant_type,
    COUNT(*)                               AS restaurant_count,
    ROUND(AVG(r.rating), 2)                AS avg_rating,
    ROUND(AVG(r.cost_for_two))             AS avg_cost_for_two,
    ROUND(AVG(r.online_order) * 100, 1)    AS pct_online_order,
    ROUND(AVG(r.book_table) * 100, 1)      AS pct_table_booking
FROM restaurant_type_map rm
JOIN restaurant_types rt ON rt.type_id      = rm.type_id
JOIN restaurants      r  ON r.restaurant_id = rm.restaurant_id
GROUP BY rt.name
HAVING COUNT(*) >= 30
ORDER BY restaurant_count DESC;


-- ---------------------------------------------------------------------------
-- Q18. Cafes versus casual dining versus fine dining, head to head.
-- Business question: what do you actually get at each step up in formality?
-- ---------------------------------------------------------------------------
SELECT
    rt.name                                AS restaurant_type,
    COUNT(*)                               AS restaurant_count,
    ROUND(AVG(r.rating), 2)                AS avg_rating,
    ROUND(AVG(r.cost_for_two))             AS avg_cost_for_two,
    ROUND(AVG(r.votes))                    AS avg_votes,
    MAX(r.rating)                          AS best_rating
FROM restaurant_type_map rm
JOIN restaurant_types rt ON rt.type_id      = rm.type_id
JOIN restaurants      r  ON r.restaurant_id = rm.restaurant_id
WHERE rt.name IN ('Cafe', 'Casual Dining', 'Fine Dining', 'Quick Bites', 'Pub')
GROUP BY rt.name
ORDER BY avg_cost_for_two DESC;


-- ---------------------------------------------------------------------------
-- Q19. Which Zomato browse category carries the best restaurants?
-- Business question: is the Buffet list better than the Delivery list?
-- Uses restaurant_listings, the table that remembers which browse pages each
-- restaurant appeared on before we de-duplicated them.
-- ---------------------------------------------------------------------------
SELECT
    rl.listed_type                    AS browse_category,
    COUNT(DISTINCT rl.restaurant_id)  AS restaurants,
    ROUND(AVG(r.rating), 2)           AS avg_rating,
    ROUND(AVG(r.cost_for_two))        AS avg_cost_for_two
FROM restaurant_listings rl
JOIN restaurants r ON r.restaurant_id = rl.restaurant_id
WHERE r.rating IS NOT NULL
GROUP BY rl.listed_type
ORDER BY avg_rating DESC;
-- COUNT(DISTINCT ...) matters here: a restaurant can appear under the same
-- browse category on several city pages, and we only want to count it once.
