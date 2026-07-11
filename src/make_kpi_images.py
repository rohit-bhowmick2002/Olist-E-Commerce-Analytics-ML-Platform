"""
Generate KPI images / business charts by executing the SQL analytics queries
against the real Olist SQLite database.
Also produces a JSON KPI dictionary consumed by the dashboards.
"""
import json
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
DB   = ROOT / "data" / "olist.db"
IMG  = ROOT / "images"
IMG.mkdir(exist_ok=True)

sns.set_theme(style="whitegrid", context="talk")
BRAND = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B", "#6A994E"]


def q(sql: str) -> pd.DataFrame:
    with sqlite3.connect(DB) as c:
        return pd.read_sql(sql, c)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(IMG / name, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {name}")


# ---- KPI header numbers ---------------------------------------------
def kpi_headline():
    r = q("""
        SELECT
          (SELECT COUNT(DISTINCT customer_unique_id) FROM customers)             AS customers,
          (SELECT COUNT(*) FROM orders)                                           AS orders,
          (SELECT SUM(price+freight_value) FROM order_items)                      AS gmv,
          (SELECT AVG(review_score) FROM order_reviews)                           AS avg_review,
          (SELECT 100.0*SUM(CASE WHEN order_delivered_customer_date <= order_estimated_delivery_date
                                 THEN 1 ELSE 0 END)/COUNT(*)
             FROM orders WHERE order_delivered_customer_date IS NOT NULL)          AS on_time_pct,
          (SELECT AVG(payment_value) FROM order_payments)                          AS aov
    """).iloc[0].to_dict()
    kpi = {
        "customers":    int(r["customers"]),
        "orders":       int(r["orders"]),
        "gmv_brl":      round(r["gmv"], 2),
        "avg_review":   round(r["avg_review"], 2),
        "on_time_pct":  round(r["on_time_pct"], 2),
        "aov_brl":      round(r["aov"], 2),
    }
    return kpi


# ---- Charts ---------------------------------------------------------
def chart_monthly_gmv():
    df = q("""
      SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
             SUM(oi.price + oi.freight_value)              AS gmv,
             COUNT(DISTINCT o.order_id)                    AS orders
      FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
      WHERE o.order_status NOT IN ('canceled','unavailable')
        AND o.order_purchase_timestamp BETWEEN '2017-01-01' AND '2018-09-01'
      GROUP BY month ORDER BY month
    """)
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.bar(df.month, df.gmv/1000, color=BRAND[0], alpha=0.75, label="GMV (k BRL)")
    ax2 = ax1.twinx()
    ax2.plot(df.month, df.orders, color=BRAND[2], marker="o", lw=2.5, label="Orders")
    ax1.set_ylabel("GMV (thousand BRL)")
    ax2.set_ylabel("Orders")
    ax1.set_title("Monthly GMV & Order Volume")
    ax1.tick_params(axis="x", rotation=45)
    fig.legend(loc="upper left", bbox_to_anchor=(0.08, 0.95))
    save(fig, "kpi_monthly_gmv.png")


def chart_revenue_by_state():
    df = q("""
      SELECT c.customer_state,
             SUM(oi.price + oi.freight_value) AS revenue
      FROM orders o
      JOIN order_items oi ON oi.order_id = o.order_id
      JOIN customers c ON c.customer_id = o.customer_id
      GROUP BY c.customer_state ORDER BY revenue DESC LIMIT 15
    """)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(df.customer_state[::-1], df.revenue[::-1]/1000, color=BRAND[1])
    ax.set(title="Top-15 States by Revenue", xlabel="Revenue (k BRL)")
    save(fig, "kpi_revenue_state.png")


def chart_category_gmv():
    df = q("""
      SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
             SUM(oi.price + oi.freight_value) AS revenue
      FROM order_items oi
      JOIN products p ON p.product_id = oi.product_id
      LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
      GROUP BY category ORDER BY revenue DESC LIMIT 15
    """)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(df.category[::-1], df.revenue[::-1]/1000, color=BRAND[4])
    ax.set(title="Top-15 Product Categories by GMV", xlabel="Revenue (k BRL)")
    save(fig, "kpi_category_gmv.png")


def chart_payment_mix():
    df = q("""
      SELECT payment_type, SUM(payment_value) AS rev
      FROM order_payments GROUP BY payment_type ORDER BY rev DESC
    """)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(df.rev, labels=df.payment_type, autopct="%1.1f%%",
           colors=BRAND, startangle=90, wedgeprops={"edgecolor": "white"})
    ax.set_title("Revenue by Payment Method")
    save(fig, "kpi_payment_mix.png")


def chart_review_dist():
    df = q("SELECT review_score, COUNT(*) AS n FROM order_reviews GROUP BY review_score")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(df.review_score.astype(str), df.n, color=BRAND[2])
    ax.set(title="Review Score Distribution",
           xlabel="Score", ylabel="Reviews")
    for i, v in enumerate(df.n):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=11)
    save(fig, "kpi_review_dist.png")


def chart_delivery_vs_review():
    df = q("""
      SELECT CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
                  THEN 'Late' ELSE 'On-Time' END AS bucket,
             AVG(r.review_score) AS avg_review,
             COUNT(*) AS n
      FROM orders o JOIN order_reviews r ON r.order_id = o.order_id
      WHERE o.order_delivered_customer_date IS NOT NULL GROUP BY bucket
    """)
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(df.bucket, df.avg_review, color=[BRAND[3], BRAND[5]])
    ax.set(title="Delivery Punctuality vs. Avg Review Score",
           ylabel="Avg review score", ylim=(0, 5))
    for b, v in zip(bars, df.avg_review):
        ax.text(b.get_x()+b.get_width()/2, v+0.05, f"{v:.2f}",
                ha="center", fontsize=13, fontweight="bold")
    save(fig, "kpi_delivery_vs_review.png")


def chart_dow_heatmap():
    df = q("""
      SELECT CAST(strftime('%w', order_purchase_timestamp) AS INT) AS dow,
             CAST(strftime('%H', order_purchase_timestamp) AS INT) AS hour,
             COUNT(*) AS orders
      FROM orders GROUP BY dow, hour
    """)
    piv = df.pivot(index="dow", columns="hour", values="orders").fillna(0)
    piv.index = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
    fig, ax = plt.subplots(figsize=(13, 5))
    sns.heatmap(piv, cmap="YlOrRd", cbar_kws={"label": "Orders"}, ax=ax)
    ax.set(title="Order Volume by Weekday × Hour", xlabel="Hour", ylabel="Day")
    save(fig, "kpi_dow_heatmap.png")


def chart_rfm_segments():
    sql = """
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
    SELECT CASE
             WHEN R<=2 AND F<=2 AND M<=2 THEN 'Champions'
             WHEN R<=2 AND F<=3           THEN 'Loyal'
             WHEN R<=2                    THEN 'Potential Loyalist'
             WHEN R=3                     THEN 'At Risk'
             WHEN R>=4 AND F<=2           THEN 'Hibernating'
             ELSE 'Lost'
           END AS segment,
           COUNT(*) AS customers,
           ROUND(AVG(monetary),2) AS avg_monetary
    FROM rfm GROUP BY segment ORDER BY customers DESC
    """
    df = q(sql)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    ax1.pie(df.customers, labels=df.segment, autopct="%1.1f%%",
            colors=BRAND, startangle=90, wedgeprops={"edgecolor": "white"})
    ax1.set_title("Customer RFM Segments — Share")
    ax2.barh(df.segment[::-1], df.avg_monetary[::-1], color=BRAND[0])
    ax2.set(title="Avg Monetary per Segment (BRL)", xlabel="BRL")
    save(fig, "kpi_rfm_segments.png")


def chart_ontime_by_state():
    df = q("""
      SELECT c.customer_state,
             100.0*SUM(CASE WHEN o.order_delivered_customer_date <=
                                 o.order_estimated_delivery_date THEN 1 ELSE 0 END)
                   /COUNT(*) AS on_time_pct,
             COUNT(*) AS n
      FROM orders o JOIN customers c ON c.customer_id = o.customer_id
      WHERE o.order_delivered_customer_date IS NOT NULL
      GROUP BY c.customer_state ORDER BY on_time_pct
    """)
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = ["#C73E1D" if p < 88 else "#F18F01" if p < 92 else "#6A994E" for p in df.on_time_pct]
    ax.barh(df.customer_state, df.on_time_pct, color=colors)
    ax.axvline(90, ls="--", color="grey")
    ax.set(title="On-Time Delivery % by State (dashed=90% target)",
           xlabel="On-time %", xlim=(70, 100))
    save(fig, "kpi_ontime_state.png")


def chart_installments():
    df = q("""
      SELECT payment_installments AS n, COUNT(*) AS orders
      FROM order_payments WHERE payment_type='credit_card'
      GROUP BY n ORDER BY n
    """)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(df.n.astype(str), df.orders, color=BRAND[1])
    ax.set(title="Credit-Card Installments Chosen", xlabel="Installments",
           ylabel="Orders")
    save(fig, "kpi_installments.png")


def chart_cohort_heatmap():
    df = q("""
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
             COUNT(DISTINCT a.customer_unique_id) AS active
      FROM firsts f JOIN activity a ON a.customer_unique_id = f.customer_unique_id
      GROUP BY f.cohort, a.active_month
    """)
    df = df[df.cohort >= "2017-01"]
    piv = df.pivot(index="cohort", columns="active_month", values="active")
    # Convert to retention %
    base = piv.max(axis=1)
    ret  = piv.div(base, axis=0) * 100
    fig, ax = plt.subplots(figsize=(13, 8))
    sns.heatmap(ret, cmap="Blues", annot=False, cbar_kws={"label": "% retained"}, ax=ax)
    ax.set(title="Cohort Retention Heatmap (% of cohort active by month)",
           xlabel="Active month", ylabel="Cohort")
    save(fig, "kpi_cohort_retention.png")


def main():
    print("Generating KPI images ...")
    kpi = kpi_headline()
    print("  headline:", kpi)
    chart_monthly_gmv()
    chart_revenue_by_state()
    chart_category_gmv()
    chart_payment_mix()
    chart_review_dist()
    chart_delivery_vs_review()
    chart_dow_heatmap()
    chart_rfm_segments()
    chart_ontime_by_state()
    chart_installments()
    chart_cohort_heatmap()
    with open(ROOT / "images" / "kpi_headline.json", "w") as f:
        json.dump(kpi, f, indent=2)
    print("Done.")


if __name__ == "__main__":
    main()
