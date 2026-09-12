# Power BI reference sheet

What you have to work with, and the traps. No instructions on what to build.

---

## The four tables

### `vw_bi_restaurants` — your main table, 12,464 rows, one per restaurant

| Field | Type | Notes |
|---|---|---|
| `restaurant_id` | number | the key that links to the other tables |
| `restaurant` | text | the name |
| `address` | text | long, better in a tooltip than on a chart |
| `area` | text | 93 neighbourhoods, e.g. Koramangala 5th Block |
| `cost_for_two` | number | rupees. **Blank for 87 restaurants** |
| `rating` | number | 1.8 to 4.9. **Blank for 3,011 restaurants** |
| `votes` | number | how many people rated it. 0 is real, never blank |
| `dish_liked` | text | popular dishes, blank for most |
| `online_order` | Yes / No | accepts online orders |
| `book_table` | Yes / No | accepts table bookings |
| `price_band` | text | 5 groups, already in price order |
| `rating_band` | text | 6 groups, already in rating order |
| `vote_band` | text | 5 groups, already in order |
| `value_score` | number | rating earned per 1000 rupees. Higher is better |
| `well_reviewed` | Yes / No | has 100 or more votes |

### `vw_bi_cuisines` — 29,269 rows

`restaurant_id`, `cuisine`. A restaurant serving three cuisines appears three times.

### `vw_bi_types` — 14,238 rows

`restaurant_id`, `restaurant_type`. Cafe, Pub, Casual Dining, Fine Dining, Quick Bites and 20 more.

### `vw_bi_listings` — 51,628 rows

`restaurant_id`, `browse_category`, `city_page`.

`browse_category` is one of seven: Buffet, Cafes, Delivery, Desserts, Dine-out, Drinks & nightlife, Pubs and bars.

`city_page` is the Zomato page a restaurant appeared on. **It is not where the restaurant is.** Use `area` for location. This field disagrees with `area` most of the time.

---

## Four traps

**1. Cross filter direction.** After loading, go to Model view and set every relationship to **Both**. Otherwise clicking a cuisine will not filter anything and the dashboard will look broken.

**2. Counting restaurants.** On the cuisine, type and listing tables, a restaurant appears many times. Use `DISTINCTCOUNT` on `restaurant_id`, never `COUNT`. Otherwise a restaurant serving four cuisines counts as four restaurants.

**3. Blank ratings.** 3,011 restaurants have no rating. Power BI ignores blanks when it averages, which is correct. But a bar chart of restaurant counts will include them, so a chart of "count" and a chart of "average rating" cover different restaurants. Say which one a chart is showing.

**4. Small groups lie.** An area with two restaurants and one 4.9 rating will top any "best area" chart. Filter to areas with enough restaurants, or add `well_reviewed = Yes` as a filter, before ranking anything by average.

---

## Measures worth creating

Right-click `vw_bi_restaurants`, choose New measure, paste one of these. A measure is a calculation that recomputes as filters change.

```
Restaurants = DISTINCTCOUNT(vw_bi_restaurants[restaurant_id])
```

```
Avg Rating = AVERAGE(vw_bi_restaurants[rating])
```

```
Avg Cost = AVERAGE(vw_bi_restaurants[cost_for_two])
```

```
Rated Restaurants = COUNT(vw_bi_restaurants[rating])
```

```
Pct Online Order =
DIVIDE(
    CALCULATE(COUNTROWS(vw_bi_restaurants), vw_bi_restaurants[online_order] = "Yes"),
    COUNTROWS(vw_bi_restaurants)
)
```

Set that last one to Percentage format in the Measure tools ribbon.

`DIVIDE` rather than `/` on purpose. It returns blank instead of an error when the bottom number is zero, which happens whenever a filter leaves a chart empty.

---

## Facts already in the data

Useful for checking your charts are right, or for captions.

| Fact | Value |
|---|---|
| Most restaurants | Whitefield, 885 |
| Best rated area, 50+ rated | Lavelle Road, 4.07 |
| Cheapest big area | BTM, ₹378 average |
| Most common cuisine | North Indian, 5,077 |
| Table booking vs not | 4.11 against 3.57 |
| Ratings by price | flat at 3.55 below ₹600, climbs to 4.14 above ₹1500 |
| Best browse category | Drinks & nightlife, 4.02 |
| Worst browse category | Delivery, 3.65 |
| Best value | Brahmin's Coffee Bar, 4.8 from 2,679 votes, ₹100 |

---

## If the data changes

Power BI holds a copy. Re-run the loader or change the views, then click **Refresh** on the Home ribbon to pull the new data in.
