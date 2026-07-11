"""
Olist E-Commerce Analytics Dashboard — Streamlit
Run:  streamlit run dashboard/app.py
"""
import pickle
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB   = ROOT / "data" / "olist.db"
ART  = ROOT / "ml" / "artifacts"

# --------------------------------------------------------------------- setup
st.set_page_config(
    page_title="Olist Analytics", page_icon="📦",
    layout="wide", initial_sidebar_state="expanded",
)

CSS = """
<style>
  .kpi-card {background:#0e1117; border:1px solid #262730; border-radius:12px;
             padding:18px; text-align:center;}
  .kpi-label{font-size:0.85rem; color:#9aa3b2; letter-spacing:.06em; text-transform:uppercase;}
  .kpi-value{font-size:1.85rem; font-weight:700; color:#fff; margin-top:6px;}
  .kpi-delta{font-size:.8rem; color:#6A994E; margin-top:2px;}
  .section-header{margin-top:1.5rem; padding-bottom:.3rem;
                  border-bottom:2px solid #2E86AB; color:#2E86AB;}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def conn():
    return sqlite3.connect(DB, check_same_thread=False)


@st.cache_data(ttl=3600)
def q(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, conn())


@st.cache_resource
def load_models():
    with open(ART / "churn_xgb.pkl", "rb") as f:
        churn = pickle.load(f)
    with open(ART / "kmeans_rfm.pkl", "rb") as f:
        seg = pickle.load(f)
    return churn, seg


# --------------------------------------------------------------------- sidebar
st.sidebar.title("📦 Olist Analytics")
page = st.sidebar.radio(
    "Navigate",
    ["🏠 Executive KPIs", "📈 Revenue & Growth", "👥 Customers & RFM",
     "🛍️ Products", "🚚 Logistics", "💳 Payments",
     "🤖 ML — Churn", "🧩 ML — Segments", "🔍 SQL Explorer"],
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Dataset:** Brazilian E-Commerce (Olist)  \n"
    "**Rows:** 1,551,698 across 9 tables  \n"
    "**Period:** 2016-09 → 2018-10")


# --------------------------------------------------------------------- helpers
def kpi_card(col, label, value, delta=""):
    with col:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>'
            f'<div class="kpi-delta">{delta}</div></div>',
            unsafe_allow_html=True)


def brl(x):
    return f"R$ {x:,.0f}" if x >= 1000 else f"R$ {x:,.2f}"


# --------------------------------------------------------------------- pages
def page_kpis():
    st.title("🏠 Executive KPI Dashboard")
    st.caption("Real Olist Brazilian E-Commerce — 2016-09 to 2018-10")

    r = q("""SELECT
        (SELECT COUNT(DISTINCT customer_unique_id) FROM customers) customers,
        (SELECT COUNT(*) FROM orders) orders,
        (SELECT SUM(price+freight_value) FROM order_items) gmv,
        (SELECT AVG(review_score) FROM order_reviews) avg_review,
        (SELECT 100.0*SUM(CASE WHEN order_delivered_customer_date <= order_estimated_delivery_date
                               THEN 1 ELSE 0 END)/COUNT(*)
           FROM orders WHERE order_delivered_customer_date IS NOT NULL) on_time,
        (SELECT AVG(payment_value) FROM order_payments) aov""").iloc[0]

    c = st.columns(6)
    kpi_card(c[0], "Unique Customers", f"{int(r.customers):,}",  "🟢 all-time")
    kpi_card(c[1], "Orders",           f"{int(r.orders):,}",     "🟢 delivered incl.")
    kpi_card(c[2], "GMV",              brl(r.gmv),                "💰 lifetime")
    kpi_card(c[3], "AOV",              brl(r.aov),                "🛒 per order")
    kpi_card(c[4], "Avg Review",       f"{r.avg_review:.2f} ⭐",   "😊 CSAT proxy")
    kpi_card(c[5], "On-Time %",        f"{r.on_time:.1f}%",        "🚚 delivery SLA")

    st.markdown("### 📈 Monthly Revenue & Order Volume")
    df = q("""SELECT strftime('%Y-%m', o.order_purchase_timestamp) month,
                     SUM(oi.price+oi.freight_value) gmv,
                     COUNT(DISTINCT o.order_id) orders
              FROM orders o JOIN order_items oi ON oi.order_id=o.order_id
              WHERE o.order_status NOT IN ('canceled','unavailable')
                AND o.order_purchase_timestamp BETWEEN '2017-01-01' AND '2018-09-01'
              GROUP BY month ORDER BY month""")
    fig = go.Figure()
    fig.add_bar(x=df.month, y=df.gmv, name="GMV (BRL)", marker_color="#2E86AB")
    fig.add_trace(go.Scatter(x=df.month, y=df.orders, name="Orders",
                             yaxis="y2", mode="lines+markers",
                             line=dict(color="#F18F01", width=3)))
    fig.update_layout(
        yaxis=dict(title="GMV (BRL)"),
        yaxis2=dict(title="Orders", overlaying="y", side="right"),
        template="plotly_dark", height=420, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    a, b = st.columns(2)
    with a:
        st.markdown("### 🗺️ Revenue by State")
        df = q("""SELECT c.customer_state state,
                         SUM(oi.price+oi.freight_value) rev
                  FROM orders o JOIN order_items oi ON oi.order_id=o.order_id
                  JOIN customers c ON c.customer_id=o.customer_id
                  GROUP BY state ORDER BY rev DESC LIMIT 12""")
        st.plotly_chart(px.bar(df, x="rev", y="state", orientation="h",
                               color="rev", color_continuous_scale="Blues",
                               template="plotly_dark").update_layout(height=400),
                        use_container_width=True)
    with b:
        st.markdown("### ⭐ Review Score")
        df = q("SELECT review_score, COUNT(*) n FROM order_reviews GROUP BY review_score")
        st.plotly_chart(px.bar(df, x="review_score", y="n",
                               color="review_score",
                               color_continuous_scale="RdYlGn",
                               template="plotly_dark").update_layout(height=400),
                        use_container_width=True)


def page_growth():
    st.title("📈 Revenue & Growth")
    df = q("""SELECT strftime('%Y-%m', o.order_purchase_timestamp) month,
                     SUM(oi.price+oi.freight_value) gmv
              FROM orders o JOIN order_items oi ON oi.order_id=o.order_id
              GROUP BY month ORDER BY month""")
    df["mom_pct"] = df.gmv.pct_change()*100
    st.plotly_chart(px.line(df, x="month", y="gmv", markers=True,
                            title="GMV Trend", template="plotly_dark"),
                    use_container_width=True)
    st.plotly_chart(px.bar(df.dropna(), x="month", y="mom_pct",
                           title="Month-over-Month %",
                           color="mom_pct",
                           color_continuous_scale="RdYlGn",
                           template="plotly_dark"),
                    use_container_width=True)

    st.markdown("### Heatmap — Orders by Weekday × Hour")
    heat = q("""SELECT CAST(strftime('%w', order_purchase_timestamp) AS INT) dow,
                       CAST(strftime('%H', order_purchase_timestamp) AS INT) hour,
                       COUNT(*) orders FROM orders GROUP BY dow, hour""")
    piv = heat.pivot(index="dow", columns="hour", values="orders").fillna(0)
    piv.index = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
    st.plotly_chart(px.imshow(piv, aspect="auto", color_continuous_scale="YlOrRd",
                              template="plotly_dark",
                              labels=dict(x="Hour", y="Day", color="Orders")),
                    use_container_width=True)


def page_customers():
    st.title("👥 Customers & RFM")
    df = q("""WITH agg AS (
        SELECT c.customer_unique_id,
               MAX(o.order_purchase_timestamp) last_order,
               COUNT(DISTINCT o.order_id) frequency,
               SUM(oi.price+oi.freight_value) monetary
        FROM orders o JOIN customers c ON c.customer_id=o.customer_id
        JOIN order_items oi ON oi.order_id=o.order_id
        WHERE o.order_status NOT IN ('canceled','unavailable')
        GROUP BY c.customer_unique_id
    ), rfm AS (
        SELECT customer_unique_id,
               CAST(julianday('2018-10-01')-julianday(last_order) AS INT) recency,
               frequency, monetary,
               NTILE(5) OVER (ORDER BY julianday(last_order) DESC) R,
               NTILE(5) OVER (ORDER BY frequency DESC) F,
               NTILE(5) OVER (ORDER BY monetary DESC) M
        FROM agg)
    SELECT CASE
             WHEN R<=2 AND F<=2 AND M<=2 THEN 'Champions'
             WHEN R<=2 AND F<=3           THEN 'Loyal'
             WHEN R<=2                    THEN 'Potential Loyalist'
             WHEN R=3                     THEN 'At Risk'
             WHEN R>=4 AND F<=2           THEN 'Hibernating'
             ELSE 'Lost'
           END segment, COUNT(*) customers,
           ROUND(AVG(monetary),2) avg_monetary,
           ROUND(AVG(recency),1) avg_recency
    FROM rfm GROUP BY segment ORDER BY customers DESC""")

    a, b = st.columns(2)
    a.plotly_chart(px.pie(df, values="customers", names="segment",
                          title="RFM Segment Share",
                          template="plotly_dark"), use_container_width=True)
    b.plotly_chart(px.bar(df, x="segment", y="avg_monetary",
                          title="Avg Monetary per Segment",
                          color="avg_monetary", color_continuous_scale="Blues",
                          template="plotly_dark"), use_container_width=True)
    st.dataframe(df, use_container_width=True)


def page_products():
    st.title("🛍️ Product Analytics")
    df = q("""SELECT COALESCE(t.product_category_name_english,p.product_category_name) category,
                     SUM(oi.price+oi.freight_value) revenue,
                     COUNT(*) units,
                     AVG(r.review_score) avg_review
              FROM order_items oi
              JOIN products p ON p.product_id=oi.product_id
              LEFT JOIN category_translation t ON t.product_category_name=p.product_category_name
              LEFT JOIN order_reviews r ON r.order_id=oi.order_id
              GROUP BY category
              ORDER BY revenue DESC LIMIT 20""")
    st.plotly_chart(px.bar(df, x="revenue", y="category", orientation="h",
                           color="avg_review", color_continuous_scale="RdYlGn",
                           title="Top-20 Categories — Revenue × Avg Review",
                           template="plotly_dark").update_layout(height=650),
                    use_container_width=True)
    st.dataframe(df.round(2), use_container_width=True)


def page_logistics():
    st.title("🚚 Logistics & Delivery")
    df = q("""SELECT c.customer_state,
                     100.0*SUM(CASE WHEN o.order_delivered_customer_date <=
                                         o.order_estimated_delivery_date
                                    THEN 1 ELSE 0 END)/COUNT(*) on_time_pct,
                     AVG(julianday(o.order_delivered_customer_date)
                        -julianday(o.order_purchase_timestamp)) avg_days
              FROM orders o JOIN customers c ON c.customer_id=o.customer_id
              WHERE o.order_delivered_customer_date IS NOT NULL
              GROUP BY c.customer_state""")
    a, b = st.columns(2)
    a.plotly_chart(px.bar(df.sort_values("on_time_pct"), x="on_time_pct",
                          y="customer_state", orientation="h",
                          color="on_time_pct", color_continuous_scale="RdYlGn",
                          title="On-Time Delivery % by State",
                          template="plotly_dark").update_layout(height=650),
                   use_container_width=True)
    b.plotly_chart(px.bar(df.sort_values("avg_days", ascending=False),
                          x="avg_days", y="customer_state", orientation="h",
                          color="avg_days", color_continuous_scale="Reds",
                          title="Avg Delivery Days by State",
                          template="plotly_dark").update_layout(height=650),
                   use_container_width=True)

    d2 = q("""SELECT CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
                          THEN 'Late' ELSE 'On-Time' END bucket,
                     AVG(r.review_score) avg_review
              FROM orders o JOIN order_reviews r ON r.order_id=o.order_id
              WHERE o.order_delivered_customer_date IS NOT NULL
              GROUP BY bucket""")
    st.plotly_chart(px.bar(d2, x="bucket", y="avg_review", color="bucket",
                           color_discrete_sequence=["#C73E1D", "#6A994E"],
                           title="Delivery punctuality → review score",
                           template="plotly_dark").update_layout(height=400),
                    use_container_width=True)


def page_payments():
    st.title("💳 Payments")
    df = q("""SELECT payment_type, COUNT(*) n, SUM(payment_value) rev,
                     AVG(payment_value) avg_ticket
              FROM order_payments GROUP BY payment_type ORDER BY rev DESC""")
    a, b = st.columns(2)
    a.plotly_chart(px.pie(df, values="rev", names="payment_type",
                          title="Revenue by Payment Method",
                          template="plotly_dark"), use_container_width=True)
    b.plotly_chart(px.bar(df, x="payment_type", y="avg_ticket",
                          title="Avg Ticket by Payment Method",
                          template="plotly_dark"), use_container_width=True)

    inst = q("""SELECT payment_installments n, COUNT(*) orders
                FROM order_payments WHERE payment_type='credit_card'
                GROUP BY n ORDER BY n""")
    st.plotly_chart(px.bar(inst, x="n", y="orders",
                           title="Credit-Card Installment Choice",
                           template="plotly_dark"),
                    use_container_width=True)


def page_churn():
    st.title("🤖 Customer Churn Prediction")
    st.markdown(
        "**Model:** XGBoost with `scale_pos_weight` for imbalance.  "
        "**Target:** customer with no order in the last 180 days.")
    a, b, c, d = st.columns(4)
    kpi_card(a, "ROC AUC",     "0.8945", "🎯 lift vs random")
    kpi_card(b, "Accuracy",    "80.5%",  "hold-out")
    kpi_card(c, "Avg Precis.", "0.947",  "PR curve")
    kpi_card(d, "Training rows","71,265", "25% test")

    a, b = st.columns(2)
    a.image(str(ROOT / "images" / "churn_roc.png"), caption="ROC curve")
    b.image(str(ROOT / "images" / "churn_pr.png"),  caption="PR curve")
    a, b = st.columns(2)
    a.image(str(ROOT / "images" / "churn_confusion.png"), caption="Confusion matrix")
    b.image(str(ROOT / "images" / "churn_feat_importance.png"), caption="Feature importance")

    st.markdown("### 🔮 Score a customer")
    m, _ = load_models()
    model, feats = m["model"], m["features"]
    with st.form("score"):
        cols = st.columns(3)
        vals = {}
        defaults = dict(frequency=1, monetary=150.0, avg_item_price=100.0,
                        avg_freight=20.0, avg_review=4.0, on_time_rate=0.9,
                        n_categories=1, avg_delivery_days=12.0, tenure_days=0)
        for i, f in enumerate(feats):
            vals[f] = cols[i % 3].number_input(f, value=float(defaults[f]))
        if st.form_submit_button("Predict churn probability"):
            proba = model.predict_proba(pd.DataFrame([vals]))[0, 1]
            st.metric("Predicted churn probability", f"{proba:.1%}",
                      "High risk" if proba > 0.6 else "Low risk")


def page_segments():
    st.title("🧩 Customer Segmentation (KMeans on RFM)")
    st.image(str(ROOT / "images" / "segments_scatter.png"))
    st.image(str(ROOT / "images" / "segments_bar.png"))


def page_sql():
    st.title("🔍 SQL Explorer")
    st.caption("Run any SELECT against the Olist database.")
    default = """SELECT c.customer_state, COUNT(*) orders,
       ROUND(SUM(oi.price+oi.freight_value),2) revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_state
ORDER BY revenue DESC
LIMIT 15;"""
    sql = st.text_area("SQL", default, height=180)
    if st.button("Run"):
        try:
            df = q(sql)
            st.success(f"{len(df):,} rows")
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(str(e))


PAGES = {
    "🏠 Executive KPIs": page_kpis,
    "📈 Revenue & Growth": page_growth,
    "👥 Customers & RFM": page_customers,
    "🛍️ Products":        page_products,
    "🚚 Logistics":        page_logistics,
    "💳 Payments":         page_payments,
    "🤖 ML — Churn":      page_churn,
    "🧩 ML — Segments":   page_segments,
    "🔍 SQL Explorer":    page_sql,
}
PAGES[page]()
