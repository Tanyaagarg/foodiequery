-- ============================================================================
-- FoodieQuery : database schema
-- ============================================================================
-- Run this once, before load_data.py. It is safe to run again: it drops the
-- tables first and rebuilds them empty.
--
-- Vocabulary used below:
--   PRIMARY KEY  the column that uniquely identifies a row. No two rows can
--                share one, and it can never be blank.
--   FOREIGN KEY  a column that must match a primary key in another table.
--                It is a promise the database enforces: you cannot save a
--                restaurant pointing at location 999 if no location 999 exists.
--   INDEX        a lookup shortcut. Without one, MySQL reads all 12,464 rows
--                to answer "rating above 4.5". With one, it jumps straight
--                to the matching rows.
--   NULL         means "we do not know". Different from 0 or empty text.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS foodiequery
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
-- utf8mb4 is the character set that can store any character, including the
-- accented names we repaired and emoji. Older utf8 in MySQL cannot.

USE foodiequery;

-- Drop in reverse order of creation. A table cannot be dropped while another
-- table still points a foreign key at it, so children go first.
DROP TABLE IF EXISTS restaurant_listings;
DROP TABLE IF EXISTS restaurant_type_map;
DROP TABLE IF EXISTS restaurant_cuisines;
DROP TABLE IF EXISTS restaurants;
DROP TABLE IF EXISTS restaurant_types;
DROP TABLE IF EXISTS cuisines;
DROP TABLE IF EXISTS locations;


-- ---------------------------------------------------------------------------
-- locations : the 93 Bangalore neighbourhoods
-- ---------------------------------------------------------------------------
-- Why a separate table instead of a text column on restaurants? Because
-- "Koramangala 5th Block" would otherwise be typed out 2,500 times. Storing
-- it once and pointing at it saves space, and makes a rename a one-row edit.
CREATE TABLE locations (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(60) NOT NULL,
    UNIQUE KEY uq_location_name (name)
    -- UNIQUE stops the same neighbourhood being inserted twice.
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- cuisines : the 107 distinct cuisines
-- ---------------------------------------------------------------------------
CREATE TABLE cuisines (
    cuisine_id INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(50) NOT NULL,
    UNIQUE KEY uq_cuisine_name (name)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- restaurant_types : the 25 formats (Cafe, Pub, Quick Bites, Fine Dining ...)
-- ---------------------------------------------------------------------------
CREATE TABLE restaurant_types (
    type_id INT AUTO_INCREMENT PRIMARY KEY,
    name    VARCHAR(40) NOT NULL,
    UNIQUE KEY uq_type_name (name)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- restaurants : the main table, one row per real restaurant
-- ---------------------------------------------------------------------------
CREATE TABLE restaurants (
    restaurant_id INT PRIMARY KEY,
    -- No AUTO_INCREMENT here: the cleaning script already assigned these IDs,
    -- and the other CSV files reference them. We must keep the same numbers.

    name          VARCHAR(120) NOT NULL,
    address       VARCHAR(300) NOT NULL,
    location_id   INT NULL,

    cost_for_two  INT NULL,
    -- NULL where Zomato had no price. Not 0, which would mean "free".

    rating        DECIMAL(2,1) NULL,
    -- DECIMAL(2,1) means 2 digits total, 1 after the point: 0.0 to 9.9.
    -- Exact, unlike FLOAT, which stores 4.1 as 4.0999999 and breaks
    -- comparisons like "rating = 4.1".

    votes         INT NOT NULL DEFAULT 0,
    -- Zero votes is a real fact here, not missing data, so NOT NULL is right.

    online_order  BOOLEAN NOT NULL DEFAULT FALSE,
    book_table    BOOLEAN NOT NULL DEFAULT FALSE,
    -- MySQL stores BOOLEAN as 1 or 0 behind the scenes.

    dish_liked    VARCHAR(300) NULL,

    CONSTRAINT fk_restaurant_location
        FOREIGN KEY (location_id) REFERENCES locations(location_id),

    -- Indexes on the columns our questions filter and sort by most.
    INDEX idx_restaurants_location (location_id),
    INDEX idx_restaurants_rating   (rating),
    INDEX idx_restaurants_cost     (cost_for_two),
    INDEX idx_restaurants_votes    (votes),
    INDEX idx_restaurants_name     (name),
    -- A combined index for the very common "good AND cheap" question.
    -- Order matters: MySQL can use this for rating alone, or rating + cost,
    -- but not for cost alone.
    INDEX idx_restaurants_rating_cost (rating, cost_for_two)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- restaurant_cuisines : the many-to-many link
-- ---------------------------------------------------------------------------
-- One restaurant serves many cuisines. One cuisine is served by many
-- restaurants. Neither table can hold the other, so this third table holds
-- the pairings, one row per pairing.
CREATE TABLE restaurant_cuisines (
    restaurant_id INT NOT NULL,
    cuisine_id    INT NOT NULL,

    PRIMARY KEY (restaurant_id, cuisine_id),
    -- A primary key across both columns means the same pairing cannot be
    -- stored twice, and lookups by restaurant are instant.

    CONSTRAINT fk_rc_restaurant
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
        ON DELETE CASCADE,
    -- CASCADE means: if a restaurant is ever deleted, its cuisine links go
    -- with it, instead of being left behind pointing at nothing.

    CONSTRAINT fk_rc_cuisine
        FOREIGN KEY (cuisine_id) REFERENCES cuisines(cuisine_id)
        ON DELETE CASCADE,

    -- The primary key already covers restaurant -> cuisine lookups.
    -- This index covers the opposite direction: "every Chinese restaurant".
    INDEX idx_rc_cuisine (cuisine_id)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- restaurant_type_map : same idea, for restaurant formats
-- ---------------------------------------------------------------------------
CREATE TABLE restaurant_type_map (
    restaurant_id INT NOT NULL,
    type_id       INT NOT NULL,

    PRIMARY KEY (restaurant_id, type_id),

    CONSTRAINT fk_rtm_restaurant
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_rtm_type
        FOREIGN KEY (type_id) REFERENCES restaurant_types(type_id)
        ON DELETE CASCADE,

    INDEX idx_rtm_type (type_id)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- restaurant_listings : which Zomato browse pages each restaurant appeared on
-- ---------------------------------------------------------------------------
-- Deliberately NOT normalised into id tables. There are only 7 listing types
-- and 30 city pages, so lookup tables would save almost no space while adding
-- two more joins to every query. Keeping readable text here also makes the AI
-- agent's generated SQL simpler and more reliable in Phase 5.
CREATE TABLE restaurant_listings (
    restaurant_id INT NOT NULL,
    listed_type   VARCHAR(30) NOT NULL,   -- Buffet, Delivery, Dine-out, Cafes ...
    listed_city   VARCHAR(60) NOT NULL,   -- the city page, NOT the real location

    PRIMARY KEY (restaurant_id, listed_type, listed_city),

    CONSTRAINT fk_rl_restaurant
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
        ON DELETE CASCADE,

    INDEX idx_rl_type (listed_type),
    INDEX idx_rl_city (listed_city)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- A convenience view for the AI agent and for Power BI
-- ---------------------------------------------------------------------------
-- A VIEW is a saved query that behaves like a table. It stores no data of its
-- own. This one flattens the joins back into one wide row per restaurant, with
-- cuisines and types as readable comma lists.
--
-- Why: in Phase 5 the AI writes its own SQL. Every join it has to get right is
-- a chance to get it wrong. For simple questions it can just read this view.
DROP VIEW IF EXISTS v_restaurants_full;
CREATE VIEW v_restaurants_full AS
SELECT
    r.restaurant_id,
    r.name,
    r.address,
    l.name                                   AS location,
    r.cost_for_two,
    r.rating,
    r.votes,
    r.online_order,
    r.book_table,
    r.dish_liked,
    GROUP_CONCAT(DISTINCT c.name  ORDER BY c.name  SEPARATOR ', ') AS cuisines,
    GROUP_CONCAT(DISTINCT rt.name ORDER BY rt.name SEPARATOR ', ') AS restaurant_types
FROM restaurants r
LEFT JOIN locations           l  ON l.location_id  = r.location_id
LEFT JOIN restaurant_cuisines rc ON rc.restaurant_id = r.restaurant_id
LEFT JOIN cuisines            c  ON c.cuisine_id   = rc.cuisine_id
LEFT JOIN restaurant_type_map rm ON rm.restaurant_id = r.restaurant_id
LEFT JOIN restaurant_types    rt ON rt.type_id     = rm.type_id
GROUP BY r.restaurant_id;
-- LEFT JOIN, not JOIN: a plain JOIN would silently drop restaurants that have
-- no cuisine listed. LEFT keeps every restaurant and leaves the gap blank.
