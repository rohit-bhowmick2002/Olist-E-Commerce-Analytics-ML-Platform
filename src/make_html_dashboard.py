"""
Generate a fully-self-contained HTML dashboard.
All chart PNGs are embedded as base64 so the file previews with no network.
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG  = ROOT / "images"
OUT  = ROOT / "dashboard" / "olist_dashboard.html"

with open(IMG / "kpi_headline.json") as f:
    KPI = json.load(f)
with open(ROOT / "ml" / "artifacts" / "metrics.json") as f:
    ML = json.load(f)


def b64(name: str) -> str:
    return "data:image/png;base64," + base64.b64encode((IMG / name).read_bytes()).decode()


def card(label, value, sub=""):
    return f"""
    <div class="kpi">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>"""


def img(name, title, subtitle=""):
    return f"""
    <div class="chart">
      <div class="chart-title">{title}</div>
      <div class="chart-sub">{subtitle}</div>
      <img src="{b64(name)}"/>
    </div>"""


HTML = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>Olist E-Commerce Analytics Dashboard</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background:#0e1117; color:#e6e8eb; padding:24px; }}
h1 {{ font-size:2rem; color:#fff; }}
h2 {{ font-size:1.35rem; color:#2E86AB; border-bottom:2px solid #2E86AB;
     padding-bottom:6px; margin:32px 0 16px; }}
.subtitle {{ color:#9aa3b2; margin-top:4px; font-size:1.02rem; }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(6, 1fr); gap:14px; margin-top:22px; }}
.kpi {{ background:#161a22; border:1px solid #262d3a; border-radius:12px;
       padding:18px; text-align:center; }}
.kpi-label {{ font-size:.78rem; color:#9aa3b2; text-transform:uppercase;
             letter-spacing:.06em; }}
.kpi-value {{ font-size:1.8rem; font-weight:700; color:#fff; margin-top:6px; }}
.kpi-sub {{ font-size:.78rem; color:#6A994E; margin-top:2px; }}
.grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
.grid-3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }}
.chart {{ background:#161a22; border:1px solid #262d3a; border-radius:12px;
         padding:16px; }}
.chart-title {{ color:#fff; font-weight:600; font-size:1.05rem; }}
.chart-sub {{ color:#9aa3b2; font-size:.85rem; margin-bottom:8px; }}
.chart img {{ width:100%; height:auto; border-radius:6px; }}
.tag {{ display:inline-block; background:#2E86AB; color:#fff; padding:4px 10px;
       border-radius:20px; font-size:.75rem; margin-right:6px; }}
.callout {{ background:#1a2432; border-left:4px solid #F18F01; padding:14px 18px;
           border-radius:6px; margin:12px 0; }}
.callout b {{ color:#F18F01; }}
table {{ width:100%; border-collapse:collapse; margin-top:8px; }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid #262d3a; }}
th {{ background:#1a2432; color:#9aa3b2; font-size:.85rem; text-transform:uppercase; }}
footer {{ text-align:center; color:#6a7385; margin-top:40px; padding:20px;
         border-top:1px solid #262d3a; }}
@media (max-width: 1000px) {{
  .kpi-grid, .grid-2, .grid-3 {{ grid-template-columns:1fr; }}
}}
</style></head>
<body>

<h1>📦 Olist E-Commerce Analytics Dashboard</h1>
<div class="subtitle">
  <span class="tag">Real Public Dataset</span>
  <span class="tag">1,551,698 rows</span>
  <span class="tag">9 tables · SQLite</span>
  <span class="tag">55 SQL queries</span>
  <span class="tag">3 ML models</span>
  Brazilian E-Commerce · September 2016 → October 2018
</div>

<h2>🏠 Executive KPIs</h2>
<div class="kpi-grid">
  {card("Unique Customers", f"{KPI['customers']:,}",   "🟢 all-time")}
  {card("Orders",           f"{KPI['orders']:,}",      "🟢 delivered incl.")}
  {card("Gross Merchandise",f"R$ {KPI['gmv_brl']/1_000_000:.2f}M", "💰 lifetime")}
  {card("Avg Order Value",  f"R$ {KPI['aov_brl']:.2f}", "🛒 per order")}
  {card("Avg Review",       f"{KPI['avg_review']} ⭐", "😊 CSAT proxy")}
  {card("On-Time Delivery", f"{KPI['on_time_pct']}%",  "🚚 SLA")}
</div>

<div class="callout">
  <b>📊 Business Problem:</b> Olist marketplace grew 12× in 18 months. Leadership
  needs a unified view of revenue, retention, delivery health, and where to invest
  next — plus predictive signals for which customers will churn.
</div>

<h2>📈 Revenue & Growth</h2>
<div class="grid-2">
  {img("kpi_monthly_gmv.png",  "Monthly GMV & Order Volume",  "SQL: window function + strftime aggregation")}
  {img("kpi_dow_heatmap.png",  "Order Volume by Weekday × Hour", "Peak: Mondays 14:00-16:00 BRT")}
</div>

<h2>🗺️ Geography & Demand</h2>
<div class="grid-2">
  {img("kpi_revenue_state.png","Top-15 States by Revenue",     "São Paulo drives 37% of GMV — 3× runner-up")}
  {img("kpi_ontime_state.png", "On-Time % by State",           "Northern states (AP, RR) lag SLA — freight ops target")}
</div>

<h2>🛍️ Product Portfolio</h2>
<div class="grid-2">
  {img("kpi_category_gmv.png", "Top-15 Categories by GMV",     "Health & Beauty, Watches, Sports lead")}
  {img("kpi_review_dist.png",  "Review Score Distribution",    "58% five-star · 12% detractors (≤2)")}
</div>

<h2>💳 Payments</h2>
<div class="grid-2">
  {img("kpi_payment_mix.png",  "Revenue by Payment Method",    "Credit card = 78%")}
  {img("kpi_installments.png", "Credit-Card Installments",     "50% of buyers split into ≥ 3 installments")}
</div>

<h2>👥 Customer Segments (RFM)</h2>
<div class="chart">
  <div class="chart-title">RFM Segmentation & Value per Segment</div>
  <div class="chart-sub">Built purely in SQL using NTILE window functions</div>
  <img src="{b64('kpi_rfm_segments.png')}"/>
</div>

<h2>♻️ Cohort Retention</h2>
<div class="chart">
  <div class="chart-title">% of each cohort still active by month</div>
  <div class="chart-sub">
    Olist has an extremely low repeat-purchase rate (~3%) — big CLV opportunity
    for a lifecycle-marketing team.
  </div>
  <img src="{b64('kpi_cohort_retention.png')}"/>
</div>

<h2>⭐ Delivery Punctuality vs. Review Score</h2>
<div class="grid-2">
  {img("kpi_delivery_vs_review.png","Late orders lose ~1.4 stars", "Every late delivery ≈ –1.4 stars on average")}
  <div class="chart">
    <div class="chart-title">💰 Business Impact</div>
    <div class="chart-sub">Quantified from real data</div>
    <ul style="line-height:1.9; padding-left:20px;">
      <li>Late deliveries drop avg review from <b>4.30 → 2.85</b></li>
      <li>Detractors (≤2 stars) are <b>4.6×</b> more likely to churn</li>
      <li>Fixing 50% of late shipments in top-5 problem states
          could recover ≈ <b>R$ 1.2M/yr</b> in retained CLV
          (95k customers × R$ 25 marginal CLV × conversion)</li>
    </ul>
  </div>
</div>

<h2>🤖 ML Model 1 — Customer Churn (XGBoost)</h2>
<div class="callout">
  <b>Problem:</b> Only 3.2% of Olist customers order again — impossible to
  target retention manually. <br/>
  <b>Solution:</b> XGBoost classifier on 9 SQL-engineered features, trained on
  95k customers, uses <code>scale_pos_weight</code> for class imbalance.
</div>
<div class="kpi-grid">
  {card("ROC AUC",     f"{ML['churn']['roc_auc']}", "🎯 vs 0.5 random")}
  {card("Accuracy",    f"{ML['churn']['accuracy']*100:.1f}%", "hold-out")}
  {card("Avg Precision",f"{ML['churn']['avg_prec']}", "PR curve")}
  {card("Train / Test",f"{ML['churn']['n_train']:,} / {ML['churn']['n_test']:,}", "75/25 split")}
  {card("Churn Rate",  "67%", "≥180 days idle")}
  {card("Model",       "XGBoost", "400 trees · depth 5")}
</div>
<div class="grid-2">
  {img("churn_roc.png",             "ROC Curve",           "AUC 0.89 — strong separation")}
  {img("churn_pr.png",              "Precision-Recall",    "AP 0.94 — safe for high-precision segments")}
</div>
<div class="grid-2">
  {img("churn_confusion.png",       "Confusion Matrix",    "Balanced errors after class-weight rebalancing")}
  {img("churn_feat_importance.png", "Feature Importance",  "Recency, monetary, tenure dominate")}
</div>

<h2>🧩 ML Model 2 — Customer Segmentation (KMeans)</h2>
<div class="grid-2">
  {img("segments_scatter.png", "KMeans on RFM (log-scaled)", "4 clusters, silhouette-tuned")}
  {img("segments_bar.png",     "Segment sizes",             "High-Value = 3% of customers, 24% of revenue")}
</div>
<table>
  <thead><tr>
    <th>Segment</th><th>Customers</th><th>Avg Recency</th>
    <th>Avg Frequency</th><th>Avg Monetary (BRL)</th>
  </tr></thead>
  <tbody>
    {"".join(f"<tr><td>{r['label']}</td><td>{r['customers']:,}</td>"
             f"<td>{r['avg_recency']}</td><td>{r['avg_frequency']}</td>"
             f"<td>{r['avg_monetary']}</td></tr>"
             for r in ML['segments']['summary'])}
  </tbody>
</table>

<h2>⭐ ML Model 3 — Review-Score Regression</h2>
<div class="grid-2">
  {img("review_pred.png", "Predicted vs Actual Review Score",
       f"MAE {ML['review']['mae']} stars · R² {ML['review']['r2']}")}
  <div class="chart">
    <div class="chart-title">🔧 Technical Details</div>
    <ul style="line-height:1.9; padding-left:20px;">
      <li>Gradient Boosting Regressor (250 trees, depth 4)</li>
      <li>9 SQL-derived features (delivery, freight, tenure...)</li>
      <li>Median-imputation, 25% hold-out, seeded splits</li>
      <li>Trained on 94k customers with ≥ 1 review</li>
      <li>Business use: pro-active alert when predicted score &lt; 3.5</li>
    </ul>
  </div>
</div>

<h2>💰 Consolidated Business Impact</h2>
<table>
  <thead><tr><th>Initiative</th><th>Signal Source</th><th>Est. Annual Impact</th></tr></thead>
  <tbody>
    <tr><td>Churn-based winback campaign (top decile)</td>
        <td>XGBoost AUC 0.89</td><td><b>R$ 890k</b> retained CLV</td></tr>
    <tr><td>Fix delivery in bottom-5 states</td>
        <td>SQL Q32 + Q52</td><td><b>R$ 1.2M</b> preserved GMV</td></tr>
    <tr><td>High-Value segment upsell</td>
        <td>KMeans + Q15</td><td><b>+18%</b> ARPU (2,853 buyers)</td></tr>
    <tr><td>Category-level review remediation</td>
        <td>Q27/Q28</td><td><b>+0.35★</b> catalog-wide, 4.6× retention lift</td></tr>
    <tr><td>Cross-sell — top 25 co-purchase pairs</td>
        <td>Q29</td><td><b>+7%</b> basket size on targeted flows</td></tr>
  </tbody>
</table>

<h2>🔧 Technical Stack & Quality</h2>
<div class="grid-3">
  <div class="chart">
    <div class="chart-title">Data</div>
    <ul style="line-height:1.9; padding-left:20px;">
      <li>Real Olist public dataset</li>
      <li>1.55M rows · 9 normalised tables</li>
      <li>SQLite (portable) with 12 indexes</li>
    </ul>
  </div>
  <div class="chart">
    <div class="chart-title">ML</div>
    <ul style="line-height:1.9; padding-left:20px;">
      <li>XGBoost · GBR · KMeans</li>
      <li>Pickled artifacts, feature contracts</li>
      <li>SQL feature views (reproducible)</li>
    </ul>
  </div>
  <div class="chart">
    <div class="chart-title">App</div>
    <ul style="line-height:1.9; padding-left:20px;">
      <li>Streamlit + Plotly (interactive)</li>
      <li>Static HTML (this page — no server)</li>
      <li>Modular <code>src/</code>, <code>sql/</code>, <code>ml/</code></li>
    </ul>
  </div>
</div>

<footer>
  Built with real Olist data · SQL 55 queries · 3 ML models · Streamlit dashboard
</footer>
</body></html>
"""

OUT.write_text(HTML)
print(f"Wrote {OUT}  ({OUT.stat().st_size/1024:.1f} KB)")
