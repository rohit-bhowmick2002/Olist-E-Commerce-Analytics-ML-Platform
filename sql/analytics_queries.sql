-- =====================================================================
-- OLIST E-COMMERCE ANALYTICS — 50+ HIGH-IMPACT SQL QUERIES
-- Database: SQLite (portable to Postgres with trivial edits)
-- Tables: customers, orders, order_items, order_payments, order_reviews,
--         products, sellers, geolocation, category_translation
-- =====================================================================

-- ============ SECTION 1: REVENUE & GROWTH KPIs (Q01–Q10) =============

-- Q01. Headline KPIs — total GMV, orders, unique customers, AOV
SELECT
    ROUND(SUM(oi.price + oi.freight_value), 2)      AS gmv_brl,
    COUNT(DISTINCT o.order_id)                       AS orders,
    COUNT(DISTINCT c.customer_unique_id)             AS unique_customers,
    ROUND(SUM(oi.price + oi.freight_value) / COUNT(DISTINCT o.order_id), 2) AS aov_brl
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers  c   ON c.customer_id = o.customer_id
WHERE o.order_status NOT IN ('canceled','unavailable');

-- Q02. Monthly GMV and order volume (trend)
SELECT
    strftime('%Y-%m', o.order_purchase_timestamp)     AS month,
    ROUND(SUM(oi.price + oi.freight_value), 2)        AS gmv,
    COUNT(DISTINCT o.order_id)                        AS orders,
    ROUND(SUM(oi.price + oi.freight_value)
          / COUNT(DISTINCT o.order_id), 2)            AS aov
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status NOT IN ('canceled','unavailable')
GROUP BY month
ORDER BY month;

-- Q03. Month-over-month GMV growth %
WITH m AS (
  SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
         SUM(oi.price + oi.freight_value) AS gmv
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.order_status NOT IN ('canceled','unavailable')
  GROUP BY month
)
SELECT month, ROUND(gmv,2) AS gmv,
       ROUND(gmv - LAG(gmv) OVER (ORDER BY month), 2)                       AS gmv_delta,
       ROUND(100.0 * (gmv - LAG(gmv) OVER (ORDER BY month))
             / LAG(gmv) OVER (ORDER BY month), 2)                            AS mom_pct
FROM m ORDER BY month;

-- Q04. Year-over-year growth
SELECT strftime('%Y', order_purchase_timestamp) AS yr,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(oi.price + oi.freight_value), 2) AS gmv
FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY yr ORDER BY yr;

-- Q05. Weekday × Hour heatmap of order volume
SELECT CAST(strftime('%w', order_purchase_timestamp) AS INT) AS dow,
       CAST(strftime('%H', order_purchase_timestamp) AS INT) AS hour,
       COUNT(*) AS orders
FROM orders GROUP BY dow, hour ORDER BY dow, hour;

-- Q06. Revenue by state (Top 15)
SELECT c.customer_state,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(oi.price + oi.freight_value), 2) AS revenue,
       ROUND(AVG(oi.price + oi.freight_value), 2) AS avg_line_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_state
ORDER BY revenue DESC LIMIT 15;

-- Q07. Top 20 cities by GMV
SELECT c.customer_city, c.customer_state,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(oi.price + oi.freight_value), 2) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_city, c.customer_state
ORDER BY revenue DESC LIMIT 20;

-- Q08. Order status distribution
SELECT order_status, COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM orders GROUP BY order_status ORDER BY orders DESC;

-- Q09. AOV trend (weekly)
SELECT strftime('%Y-%W', o.order_purchase_timestamp) AS week,
       ROUND(SUM(oi.price + oi.freight_value)/COUNT(DISTINCT o.order_id),2) AS aov,
       COUNT(DISTINCT o.order_id) AS orders
FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status NOT IN ('canceled','unavailable')
GROUP BY week ORDER BY week;

-- Q10. Rolling 30-day revenue (window function)
WITH daily AS (
  SELECT DATE(o.order_purchase_timestamp) AS d,
         SUM(oi.price + oi.freight_value) AS rev
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  GROUP BY d
)
SELECT d, ROUND(rev,2) AS rev,
       ROUND(AVG(rev) OVER (ORDER BY d ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 2) AS rev_30d_ma
FROM daily ORDER BY d;


-- ============ SECTION 2: CUSTOMER ANALYTICS & RFM (Q11–Q20) ==========

-- Q11. New vs repeat customers per month
WITH first_order AS (
  SELECT c.customer_unique_id, MIN(o.order_purchase_timestamp) AS first_ts
  FROM orders o JOIN customers c ON c.customer_id = o.customer_id
  GROUP BY c.customer_unique_id
)
SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
       SUM(CASE WHEN o.order_purchase_timestamp = f.first_ts THEN 1 ELSE 0 END) AS new_customers,
       SUM(CASE WHEN o.order_purchase_timestamp > f.first_ts THEN 1 ELSE 0 END) AS repeat_orders
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN first_order f ON f.customer_unique_id = c.customer_unique_id
GROUP BY month ORDER BY month;

-- Q12. Repeat purchase rate overall
WITH per_cust AS (
  SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS n_orders
  FROM orders o JOIN customers c ON c.customer_id = o.customer_id
  GROUP BY c.customer_unique_id
)
SELECT COUNT(*) AS customers,
       SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END)/COUNT(*), 2) AS repeat_rate_pct
FROM per_cust;

-- Q13. RFM base table (Recency, Frequency, Monetary)
WITH agg AS (
  SELECT c.customer_unique_id,
         MAX(o.order_purchase_timestamp) AS last_order,
         COUNT(DISTINCT o.order_id)      AS frequency,
         SUM(oi.price + oi.freight_value) AS monetary
  FROM orders o
  JOIN customers c ON c.customer_id = o.customer_id
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.order_status NOT IN ('canceled','unavailable')
  GROUP BY c.customer_unique_id
)
SELECT customer_unique_id,
       CAST(julianday('2018-10-01') - julianday(last_order) AS INT) AS recency_days,
       frequency,
       ROUND(monetary,2) AS monetary
FROM agg;

-- Q14. RFM segments via NTILE quintiles
WITH agg AS (
  SELECT c.customer_unique_id,
         MAX(o.order_purchase_timestamp) AS last_order,
         COUNT(DISTINCT o.order_id)      AS frequency,
         SUM(oi.price + oi.freight_value) AS monetary
  FROM orders o
  JOIN customers c ON c.customer_id = o.customer_id
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.order_status NOT IN ('canceled','unavailable')
  GROUP BY c.customer_unique_id
), rfm AS (
  SELECT customer_unique_id,
         CAST(julianday('2018-10-01') - julianday(last_order) AS INT) AS recency_days,
         frequency, monetary,
         NTILE(5) OVER (ORDER BY julianday(last_order) DESC) AS R,
         NTILE(5) OVER (ORDER BY frequency DESC)             AS F,
         NTILE(5) OVER (ORDER BY monetary DESC)              AS M
  FROM agg
)
SELECT
  CASE
    WHEN R<=2 AND F<=2 AND M<=2 THEN 'Champions'
    WHEN R<=2 AND F<=3           THEN 'Loyal'
    WHEN R<=2                    THEN 'Potential Loyalist'
    WHEN R=3                     THEN 'At Risk'
    WHEN R>=4 AND F<=2           THEN 'Hibernating'
    ELSE 'Lost'
  END AS segment,
  COUNT(*) AS customers,
  ROUND(AVG(monetary),2) AS avg_monetary,
  ROUND(AVG(recency_days),1) AS avg_recency
FROM rfm GROUP BY segment ORDER BY customers DESC;

-- Q15. Top 100 customers by lifetime revenue
SELECT c.customer_unique_id,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(oi.price + oi.freight_value), 2) AS clv
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY c.customer_unique_id
ORDER BY clv DESC LIMIT 100;

-- Q16. Distribution of orders per customer
SELECT n_orders, COUNT(*) AS customers FROM (
  SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS n_orders
  FROM orders o JOIN customers c ON c.customer_id = o.customer_id
  GROUP BY c.customer_unique_id
) GROUP BY n_orders ORDER BY n_orders;

-- Q17. Average days between orders (repeat customers)
WITH ord AS (
  SELECT c.customer_unique_id, o.order_purchase_timestamp,
         LAG(o.order_purchase_timestamp) OVER
           (PARTITION BY c.customer_unique_id ORDER BY o.order_purchase_timestamp) AS prev_ts
  FROM orders o JOIN customers c ON c.customer_id = o.customer_id
)
SELECT ROUND(AVG(julianday(order_purchase_timestamp)-julianday(prev_ts)),1) AS avg_days_between_orders
FROM ord WHERE prev_ts IS NOT NULL;

-- Q18. Cohort retention — % of a cohort that ordered again in month N
WITH firsts AS (
  SELECT c.customer_unique_id,
         strftime('%Y-%m', MIN(o.order_purchase_timestamp)) AS cohort
  FROM orders o JOIN customers c ON c.customer_id = o.customer_id
  GROUP BY c.customer_unique_id
),
activity AS (
  SELECT c.customer_unique_id,
         strftime('%Y-%m', o.order_purchase_timestamp) AS active_month
  FROM orders o JOIN customers c ON c.customer_id = o.customer_id
  GROUP BY c.customer_unique_id, active_month
)
SELECT f.cohort, a.active_month,
       COUNT(DISTINCT a.customer_unique_id) AS active_customers
FROM firsts f
JOIN activity a ON a.customer_unique_id = f.customer_unique_id
GROUP BY f.cohort, a.active_month
ORDER BY f.cohort, a.active_month;

-- Q19. State-level customer concentration (Pareto)
WITH s AS (
  SELECT c.customer_state,
         COUNT(DISTINCT c.customer_unique_id) AS customers
  FROM customers c GROUP BY c.customer_state
)
SELECT customer_state, customers,
       ROUND(100.0 * customers / SUM(customers) OVER (), 2) AS pct,
       ROUND(100.0 * SUM(customers) OVER (ORDER BY customers DESC)
             / SUM(customers) OVER (), 2) AS cum_pct
FROM s ORDER BY customers DESC;

-- Q20. Estimated 12-month CLV per state
SELECT c.customer_state,
       COUNT(DISTINCT c.customer_unique_id) AS customers,
       ROUND(SUM(oi.price + oi.freight_value)
             / COUNT(DISTINCT c.customer_unique_id), 2) AS avg_clv
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY c.customer_state
ORDER BY avg_clv DESC;


-- ============ SECTION 3: PRODUCT & CATEGORY (Q21–Q30) ================

-- Q21. Top 20 categories by GMV (translated)
SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       COUNT(DISTINCT oi.order_id) AS orders,
       ROUND(SUM(oi.price + oi.freight_value), 2) AS revenue,
       ROUND(AVG(oi.price), 2) AS avg_price
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
GROUP BY category ORDER BY revenue DESC LIMIT 20;

-- Q22. Top 20 products by units sold
SELECT oi.product_id,
       COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       COUNT(*) AS units_sold,
       ROUND(SUM(oi.price), 2) AS revenue
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
GROUP BY oi.product_id, category ORDER BY units_sold DESC LIMIT 20;

-- Q23. Price distribution per category (median-ish via NTILE approximation)
SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       ROUND(MIN(oi.price),2) AS min_price,
       ROUND(AVG(oi.price),2) AS avg_price,
       ROUND(MAX(oi.price),2) AS max_price,
       COUNT(*) AS n
FROM order_items oi JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
GROUP BY category HAVING n > 100 ORDER BY avg_price DESC LIMIT 25;

-- Q24. Category × month seasonality
SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
       COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       COUNT(*) AS units, ROUND(SUM(oi.price),2) AS revenue
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
WHERE p.product_category_name IN
  ('cama_mesa_banho','beleza_saude','esporte_lazer','moveis_decoracao','informatica_acessorios')
GROUP BY month, category ORDER BY month, category;

-- Q25. Price vs freight ratio per category
SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       ROUND(AVG(oi.freight_value),2) AS avg_freight,
       ROUND(AVG(oi.price),2)          AS avg_price,
       ROUND(AVG(oi.freight_value / NULLIF(oi.price,0)) * 100, 2) AS freight_pct_of_price
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
GROUP BY category HAVING COUNT(*) > 200 ORDER BY freight_pct_of_price DESC LIMIT 20;

-- Q26. Heavy / bulky products (impact on freight)
SELECT p.product_id,
       p.product_weight_g,
       p.product_length_cm * p.product_height_cm * p.product_width_cm AS volume_cm3,
       ROUND(AVG(oi.freight_value),2) AS avg_freight,
       COUNT(*) AS sold
FROM products p JOIN order_items oi ON oi.product_id = p.product_id
WHERE p.product_weight_g IS NOT NULL
GROUP BY p.product_id HAVING sold > 20
ORDER BY avg_freight DESC LIMIT 20;

-- Q27. Product review score by category
SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       ROUND(AVG(r.review_score),2) AS avg_score,
       COUNT(*) AS reviews
FROM order_reviews r
JOIN order_items oi ON oi.order_id = r.order_id
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
GROUP BY category HAVING reviews > 200 ORDER BY avg_score DESC LIMIT 20;

-- Q28. Worst-rated categories (retention risk)
SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       ROUND(AVG(r.review_score),2) AS avg_score,
       COUNT(*) AS reviews
FROM order_reviews r
JOIN order_items oi ON oi.order_id = r.order_id
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
GROUP BY category HAVING reviews > 200 ORDER BY avg_score ASC LIMIT 15;

-- Q29. Cross-sell — categories most frequently bought together
WITH pair AS (
  SELECT a.order_id, a.product_id AS p1, b.product_id AS p2
  FROM order_items a JOIN order_items b
    ON a.order_id = b.order_id AND a.product_id < b.product_id
)
SELECT p1.product_category_name AS cat_a,
       p2.product_category_name AS cat_b,
       COUNT(*) AS co_purchases
FROM pair
JOIN products p1 ON p1.product_id = pair.p1
JOIN products p2 ON p2.product_id = pair.p2
WHERE p1.product_category_name IS NOT NULL AND p2.product_category_name IS NOT NULL
GROUP BY cat_a, cat_b ORDER BY co_purchases DESC LIMIT 25;

-- Q30. Long-tail catalog analysis (Pareto on products)
WITH s AS (
  SELECT product_id, SUM(price) AS rev FROM order_items GROUP BY product_id
), r AS (
  SELECT product_id, rev,
         ROW_NUMBER() OVER (ORDER BY rev DESC) AS rn,
         COUNT(*)   OVER () AS total,
         SUM(rev)   OVER () AS total_rev
  FROM s
)
SELECT
  ROUND(100.0*rn/total,1)          AS pct_products,
  ROUND(100.0*SUM(rev) OVER (ORDER BY rn)/total_rev,1) AS pct_cum_revenue
FROM r WHERE rn IN (
  CAST(total*0.01 AS INT), CAST(total*0.05 AS INT),
  CAST(total*0.10 AS INT), CAST(total*0.20 AS INT),
  CAST(total*0.50 AS INT), total);


-- ============ SECTION 4: LOGISTICS & DELIVERY (Q31–Q38) ==============

-- Q31. Average actual vs estimated delivery days
SELECT
  ROUND(AVG(julianday(order_delivered_customer_date)-julianday(order_purchase_timestamp)),1)
    AS avg_actual_days,
  ROUND(AVG(julianday(order_estimated_delivery_date)-julianday(order_purchase_timestamp)),1)
    AS avg_estimated_days,
  ROUND(AVG(julianday(order_estimated_delivery_date)-julianday(order_delivered_customer_date)),1)
    AS avg_days_early
FROM orders WHERE order_delivered_customer_date IS NOT NULL;

-- Q32. On-time delivery rate by state
SELECT c.customer_state,
       COUNT(*) AS deliveries,
       SUM(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                THEN 1 ELSE 0 END) AS on_time,
       ROUND(100.0*SUM(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                            THEN 1 ELSE 0 END)/COUNT(*),2) AS on_time_pct
FROM orders o JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state ORDER BY on_time_pct;

-- Q33. Late delivery impact on review score
SELECT CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
            THEN 'Late' ELSE 'On-Time' END AS delivery_bucket,
       ROUND(AVG(r.review_score),2) AS avg_review,
       COUNT(*) AS n
FROM orders o
JOIN order_reviews r ON r.order_id = o.order_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY delivery_bucket;

-- Q34. Distribution of delivery time (days)
SELECT CAST(julianday(order_delivered_customer_date)-julianday(order_purchase_timestamp) AS INT) AS days,
       COUNT(*) AS orders
FROM orders WHERE order_delivered_customer_date IS NOT NULL
GROUP BY days ORDER BY days LIMIT 60;

-- Q35. Freight cost by state (customer side)
SELECT c.customer_state,
       ROUND(AVG(oi.freight_value),2) AS avg_freight,
       ROUND(SUM(oi.freight_value),2) AS total_freight
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_state ORDER BY avg_freight DESC;

-- Q36. Seller processing time (purchase → approved → carrier handoff)
SELECT ROUND(AVG(julianday(order_approved_at)-julianday(order_purchase_timestamp))*24,1)
         AS avg_approval_hours,
       ROUND(AVG(julianday(order_delivered_carrier_date)-julianday(order_approved_at)),1)
         AS avg_handoff_days
FROM orders
WHERE order_approved_at IS NOT NULL AND order_delivered_carrier_date IS NOT NULL;

-- Q37. Cross-state shipping share (seller state ≠ customer state)
SELECT
  SUM(CASE WHEN s.seller_state != c.customer_state THEN 1 ELSE 0 END) AS cross_state,
  SUM(CASE WHEN s.seller_state  = c.customer_state THEN 1 ELSE 0 END) AS same_state,
  ROUND(100.0*SUM(CASE WHEN s.seller_state != c.customer_state THEN 1 ELSE 0 END)
        /COUNT(*),2) AS cross_state_pct
FROM order_items oi
JOIN sellers s ON s.seller_id = oi.seller_id
JOIN orders o ON o.order_id = oi.order_id
JOIN customers c ON c.customer_id = o.customer_id;

-- Q38. Delivery time — same-state vs cross-state
SELECT CASE WHEN s.seller_state = c.customer_state THEN 'Same State' ELSE 'Cross State' END AS route,
       ROUND(AVG(julianday(o.order_delivered_customer_date)-julianday(o.order_purchase_timestamp)),1) AS avg_days,
       COUNT(*) AS n
FROM order_items oi
JOIN sellers s ON s.seller_id = oi.seller_id
JOIN orders o ON o.order_id = oi.order_id
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY route;


-- ============ SECTION 5: PAYMENTS & FINANCE (Q39–Q44) ================

-- Q39. Payment method mix
SELECT payment_type, COUNT(*) AS payments,
       ROUND(SUM(payment_value),2) AS revenue,
       ROUND(AVG(payment_value),2) AS avg_ticket,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS share_pct
FROM order_payments GROUP BY payment_type ORDER BY revenue DESC;

-- Q40. Credit-card installment behaviour
SELECT payment_installments AS installments,
       COUNT(*) AS n,
       ROUND(AVG(payment_value),2) AS avg_amount,
       ROUND(SUM(payment_value),2) AS revenue
FROM order_payments WHERE payment_type='credit_card'
GROUP BY installments ORDER BY installments;

-- Q41. AOV by payment method
SELECT payment_type,
       ROUND(AVG(payment_value),2) AS avg_ticket,
       ROUND(SUM(payment_value),2) AS revenue
FROM order_payments GROUP BY payment_type ORDER BY avg_ticket DESC;

-- Q42. Voucher usage (discount proxy)
SELECT COUNT(*) AS voucher_payments,
       ROUND(SUM(payment_value),2) AS voucher_value,
       ROUND(AVG(payment_value),2) AS avg_voucher
FROM order_payments WHERE payment_type='voucher';

-- Q43. Orders paid in > 1 method (split-tender)
WITH multi AS (
  SELECT order_id, COUNT(DISTINCT payment_type) AS n_methods
  FROM order_payments GROUP BY order_id
)
SELECT n_methods, COUNT(*) AS orders FROM multi GROUP BY n_methods ORDER BY n_methods;

-- Q44. Monthly revenue by payment type
SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
       p.payment_type,
       ROUND(SUM(p.payment_value),2) AS revenue
FROM order_payments p JOIN orders o ON o.order_id = p.order_id
GROUP BY month, p.payment_type ORDER BY month, revenue DESC;


-- ============ SECTION 6: SELLER PERFORMANCE (Q45–Q48) ================

-- Q45. Top 20 sellers by GMV
SELECT s.seller_id, s.seller_state,
       COUNT(DISTINCT oi.order_id) AS orders,
       ROUND(SUM(oi.price + oi.freight_value),2) AS gmv,
       ROUND(AVG(r.review_score),2) AS avg_review
FROM order_items oi
JOIN sellers s ON s.seller_id = oi.seller_id
LEFT JOIN order_reviews r ON r.order_id = oi.order_id
GROUP BY s.seller_id, s.seller_state
ORDER BY gmv DESC LIMIT 20;

-- Q46. Seller state distribution
SELECT seller_state, COUNT(*) AS sellers FROM sellers
GROUP BY seller_state ORDER BY sellers DESC;

-- Q47. Seller performance quintiles (revenue, on-time %, review)
WITH s AS (
  SELECT oi.seller_id,
         SUM(oi.price + oi.freight_value) AS gmv,
         AVG(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                  THEN 1.0 ELSE 0 END) AS on_time_rate,
         AVG(r.review_score) AS avg_score
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN order_reviews r ON r.order_id = oi.order_id
  WHERE o.order_delivered_customer_date IS NOT NULL
  GROUP BY oi.seller_id
), q AS (
  SELECT seller_id, gmv, on_time_rate, avg_score,
         NTILE(5) OVER (ORDER BY gmv DESC) AS gmv_quintile
  FROM s
)
SELECT gmv_quintile,
       COUNT(*) AS sellers,
       ROUND(AVG(gmv),2) AS avg_gmv,
       ROUND(AVG(on_time_rate)*100,2) AS avg_on_time_pct,
       ROUND(AVG(avg_score),2) AS avg_review
FROM q GROUP BY gmv_quintile ORDER BY gmv_quintile;

-- Q48. Long-tail sellers — % of sellers driving 80% of GMV
WITH s AS (
  SELECT seller_id, SUM(price+freight_value) AS gmv
  FROM order_items GROUP BY seller_id
), r AS (
  SELECT seller_id, gmv,
         ROW_NUMBER() OVER (ORDER BY gmv DESC) AS rn,
         SUM(gmv) OVER () AS total,
         SUM(gmv) OVER (ORDER BY gmv DESC) AS cum
  FROM s
)
SELECT COUNT(*) AS sellers_making_80pct
FROM r WHERE cum <= 0.8 * total;


-- ============ SECTION 7: REVIEWS & CX (Q49–Q52) ======================

-- Q49. Review score distribution
SELECT review_score, COUNT(*) AS n,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS pct
FROM order_reviews GROUP BY review_score ORDER BY review_score;

-- Q50. Detractors (1-2 star) vs promoters (5 star) monthly
SELECT strftime('%Y-%m', review_creation_date) AS month,
       SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) AS detractors,
       SUM(CASE WHEN review_score  = 5 THEN 1 ELSE 0 END) AS promoters,
       COUNT(*) AS total,
       ROUND(100.0*SUM(CASE WHEN review_score=5 THEN 1 ELSE 0 END)/COUNT(*),2) AS promoter_pct
FROM order_reviews GROUP BY month ORDER BY month;

-- Q51. Average time to review response
SELECT ROUND(AVG(julianday(review_answer_timestamp)-julianday(review_creation_date))*24,1)
  AS avg_response_hours
FROM order_reviews
WHERE review_answer_timestamp IS NOT NULL AND review_creation_date IS NOT NULL;

-- Q52. Correlation-proxy: delivery lateness (days) × review score
SELECT CAST(julianday(o.order_delivered_customer_date)
            - julianday(o.order_estimated_delivery_date) AS INT) AS lateness_days,
       ROUND(AVG(r.review_score),2) AS avg_score,
       COUNT(*) AS n
FROM orders o JOIN order_reviews r ON r.order_id = o.order_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY lateness_days HAVING n > 30
ORDER BY lateness_days;

-- ============ SECTION 8: CHURN & ML-FEATURE VIEWS (Q53–Q55) ==========

-- Q53. Churn-flag feature table — customer has not ordered in 180 days
WITH last_ord AS (
  SELECT c.customer_unique_id, MAX(o.order_purchase_timestamp) AS last_ts
  FROM orders o JOIN customers c ON c.customer_id = o.customer_id
  GROUP BY c.customer_unique_id
)
SELECT customer_unique_id,
       last_ts,
       CAST(julianday('2018-10-01')-julianday(last_ts) AS INT) AS recency_days,
       CASE WHEN julianday('2018-10-01')-julianday(last_ts) > 180 THEN 1 ELSE 0 END AS churn_flag
FROM last_ord;

-- Q54. Feature-engineered ML training view (per customer)
WITH base AS (
  SELECT c.customer_unique_id,
         COUNT(DISTINCT o.order_id) AS frequency,
         SUM(oi.price + oi.freight_value) AS monetary,
         AVG(oi.price) AS avg_item_price,
         AVG(oi.freight_value) AS avg_freight,
         AVG(r.review_score) AS avg_review,
         MAX(o.order_purchase_timestamp) AS last_ts,
         MIN(o.order_purchase_timestamp) AS first_ts,
         AVG(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                  THEN 1.0 ELSE 0 END) AS on_time_rate,
         COUNT(DISTINCT p.product_category_name) AS n_categories
  FROM orders o
  JOIN customers c ON c.customer_id = o.customer_id
  JOIN order_items oi ON oi.order_id = o.order_id
  JOIN products p ON p.product_id = oi.product_id
  LEFT JOIN order_reviews r ON r.order_id = o.order_id
  GROUP BY c.customer_unique_id
)
SELECT customer_unique_id, frequency, ROUND(monetary,2) AS monetary,
       ROUND(avg_item_price,2) AS avg_item_price,
       ROUND(avg_freight,2) AS avg_freight,
       ROUND(avg_review,2)  AS avg_review,
       CAST(julianday('2018-10-01')-julianday(last_ts) AS INT) AS recency_days,
       CAST(julianday(last_ts)-julianday(first_ts) AS INT)     AS tenure_days,
       ROUND(on_time_rate,3) AS on_time_rate,
       n_categories,
       CASE WHEN julianday('2018-10-01')-julianday(last_ts) > 180 THEN 1 ELSE 0 END AS churn_flag
FROM base;

-- Q55. Executive KPI snapshot (single row for dashboard header)
SELECT
  (SELECT COUNT(DISTINCT customer_unique_id) FROM customers)                         AS total_customers,
  (SELECT COUNT(*) FROM orders)                                                       AS total_orders,
  (SELECT ROUND(SUM(price+freight_value),2) FROM order_items)                         AS gmv,
  (SELECT ROUND(AVG(review_score),2) FROM order_reviews)                              AS avg_review,
  (SELECT ROUND(100.0*SUM(CASE WHEN order_delivered_customer_date <= order_estimated_delivery_date
                               THEN 1 ELSE 0 END)/COUNT(*),2)
     FROM orders WHERE order_delivered_customer_date IS NOT NULL)                     AS on_time_pct;
