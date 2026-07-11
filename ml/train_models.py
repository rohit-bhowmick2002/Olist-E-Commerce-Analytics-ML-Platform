"""
ML pipeline for Olist:
  1) Customer churn classification  (XGBoost + class weights)
  2) Review-score regression         (Gradient Boosting)
  3) Customer segmentation (KMeans)  on RFM

Outputs: trained models (pickle), evaluation report (JSON + PNG images).
"""
import json
import pickle
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    mean_absolute_error, r2_score, roc_auc_score, roc_curve,
    precision_recall_curve, average_precision_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
DB   = ROOT / "data" / "olist.db"
IMG  = ROOT / "images"
MODELS = ROOT / "ml" / "artifacts"
IMG.mkdir(parents=True, exist_ok=True)
MODELS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="talk")


# ---------------------------------------------------------------------
def load_feature_frame() -> pd.DataFrame:
    q = """
    WITH base AS (
      SELECT c.customer_unique_id,
             c.customer_state,
             COUNT(DISTINCT o.order_id)                         AS frequency,
             SUM(oi.price + oi.freight_value)                   AS monetary,
             AVG(oi.price)                                      AS avg_item_price,
             AVG(oi.freight_value)                              AS avg_freight,
             AVG(r.review_score)                                AS avg_review,
             MAX(o.order_purchase_timestamp)                    AS last_ts,
             MIN(o.order_purchase_timestamp)                    AS first_ts,
             AVG(CASE WHEN o.order_delivered_customer_date <=
                           o.order_estimated_delivery_date
                      THEN 1.0 ELSE 0 END)                      AS on_time_rate,
             COUNT(DISTINCT p.product_category_name)            AS n_categories,
             AVG(CAST(julianday(o.order_delivered_customer_date)
                     - julianday(o.order_purchase_timestamp) AS FLOAT))
                                                                AS avg_delivery_days
      FROM orders o
      JOIN customers   c  ON c.customer_id  = o.customer_id
      JOIN order_items oi ON oi.order_id    = o.order_id
      JOIN products    p  ON p.product_id   = oi.product_id
      LEFT JOIN order_reviews r ON r.order_id = o.order_id
      WHERE o.order_status NOT IN ('canceled','unavailable')
      GROUP BY c.customer_unique_id, c.customer_state
    )
    SELECT customer_unique_id, customer_state,
           frequency, monetary, avg_item_price, avg_freight,
           avg_review, on_time_rate, n_categories, avg_delivery_days,
           CAST(julianday('2018-10-01') - julianday(last_ts) AS INT) AS recency_days,
           CAST(julianday(last_ts)      - julianday(first_ts) AS INT) AS tenure_days,
           CASE WHEN julianday('2018-10-01') - julianday(last_ts) > 180
                THEN 1 ELSE 0 END AS churn_flag
    FROM base
    """
    with sqlite3.connect(DB) as c:
        df = pd.read_sql(q, c)
    return df


# ---------------------------------------------------------------------
def train_churn(df: pd.DataFrame) -> dict:
    feat = ["frequency", "monetary", "avg_item_price", "avg_freight",
            "avg_review", "on_time_rate", "n_categories",
            "avg_delivery_days", "tenure_days"]
    X = df[feat].fillna(df[feat].median())
    y = df["churn_flag"]

    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y)

    pos = (ytr == 1).sum()
    neg = (ytr == 0).sum()
    scale = neg / max(pos, 1)

    model = XGBClassifier(
        n_estimators=400, max_depth=5, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.9,
        scale_pos_weight=scale, eval_metric="auc",
        n_jobs=-1, random_state=42, tree_method="hist",
    )
    model.fit(Xtr, ytr)
    proba = model.predict_proba(Xte)[:, 1]
    pred  = (proba >= 0.5).astype(int)

    metrics = {
        "accuracy":  round(accuracy_score(yte, pred), 4),
        "roc_auc":   round(roc_auc_score(yte, proba), 4),
        "avg_prec":  round(average_precision_score(yte, proba), 4),
        "report":    classification_report(yte, pred, output_dict=True),
        "n_train":   int(len(Xtr)),
        "n_test":    int(len(Xte)),
        "class_balance": {"churn": int(pos), "active": int(neg)},
    }

    # ---- plots -------------------------------------------------------
    fpr, tpr, _ = roc_curve(yte, proba)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(fpr, tpr, lw=3, color="#2E86AB",
            label=f"XGBoost  AUC = {metrics['roc_auc']:.3f}")
    ax.plot([0, 1], [0, 1], "--", color="grey")
    ax.set(xlabel="False Positive Rate", ylabel="True Positive Rate",
           title="Churn Model — ROC Curve")
    ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(IMG / "churn_roc.png", dpi=140); plt.close(fig)

    cm = confusion_matrix(yte, pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt=",d", cmap="Blues", cbar=False,
                xticklabels=["Active", "Churn"],
                yticklabels=["Active", "Churn"], ax=ax)
    ax.set(xlabel="Predicted", ylabel="Actual",
           title="Churn Model — Confusion Matrix")
    fig.tight_layout(); fig.savefig(IMG / "churn_confusion.png", dpi=140); plt.close(fig)

    imp = pd.DataFrame({"feature": feat, "importance": model.feature_importances_}) \
            .sort_values("importance", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(imp.feature, imp.importance, color="#A23B72")
    ax.set(title="Churn Model — Feature Importance", xlabel="Importance")
    fig.tight_layout(); fig.savefig(IMG / "churn_feat_importance.png", dpi=140); plt.close(fig)

    prec, rec, _ = precision_recall_curve(yte, proba)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(rec, prec, lw=3, color="#F18F01",
            label=f"AP = {metrics['avg_prec']:.3f}")
    ax.set(xlabel="Recall", ylabel="Precision",
           title="Churn Model — Precision / Recall")
    ax.legend(loc="lower left")
    fig.tight_layout(); fig.savefig(IMG / "churn_pr.png", dpi=140); plt.close(fig)

    with open(MODELS / "churn_xgb.pkl", "wb") as f:
        pickle.dump({"model": model, "features": feat}, f)
    return metrics


# ---------------------------------------------------------------------
def train_review_regressor(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["avg_review"]).copy()
    feat = ["frequency", "monetary", "avg_item_price", "avg_freight",
            "on_time_rate", "n_categories",
            "avg_delivery_days", "tenure_days", "recency_days"]
    X = d[feat].fillna(d[feat].median())
    y = d["avg_review"]

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42)
    model = GradientBoostingRegressor(
        n_estimators=250, max_depth=4, learning_rate=0.06, random_state=42)
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)

    metrics = {
        "mae": round(mean_absolute_error(yte, pred), 4),
        "r2":  round(r2_score(yte, pred), 4),
        "n":   int(len(d)),
    }

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.hexbin(yte, pred, gridsize=30, cmap="viridis")
    ax.plot([1, 5], [1, 5], "--", color="red")
    ax.set(xlabel="Actual review score", ylabel="Predicted",
           title=f"Review Regressor — MAE={metrics['mae']} R²={metrics['r2']}")
    fig.tight_layout(); fig.savefig(IMG / "review_pred.png", dpi=140); plt.close(fig)

    with open(MODELS / "review_gbr.pkl", "wb") as f:
        pickle.dump({"model": model, "features": feat}, f)
    return metrics


# ---------------------------------------------------------------------
def segment_rfm(df: pd.DataFrame) -> dict:
    rfm = df[["recency_days", "frequency", "monetary"]].copy()
    rfm["monetary"] = np.log1p(rfm["monetary"])
    rfm["frequency"] = np.log1p(rfm["frequency"])
    scaler = StandardScaler()
    Z = scaler.fit_transform(rfm)

    km = KMeans(n_clusters=4, n_init=10, random_state=42).fit(Z)
    df["segment"] = km.labels_

    summary = df.groupby("segment").agg(
        customers=("customer_unique_id", "count"),
        avg_recency=("recency_days", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
    ).round(2).reset_index()

    labels = {}
    order = summary.sort_values("avg_monetary", ascending=False)["segment"].tolist()
    tag = ["High-Value", "Growing", "At-Risk", "Low-Value"]
    for s, t in zip(order, tag):
        labels[int(s)] = t
    summary["label"] = summary["segment"].map(labels)

    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(
        data=df.sample(min(20000, len(df)), random_state=1),
        x="recency_days", y="monetary", hue=df["segment"].map(labels),
        palette="Set2", alpha=0.6, ax=ax)
    ax.set(title="Customer Segmentation (KMeans on RFM)",
           yscale="log", xlabel="Recency (days)", ylabel="Monetary (BRL, log)")
    fig.tight_layout(); fig.savefig(IMG / "segments_scatter.png", dpi=140); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    seg_ct = summary.sort_values("customers", ascending=True)
    ax.barh(seg_ct["label"], seg_ct["customers"], color="#2E86AB")
    ax.set(title="Segment Sizes", xlabel="Customers")
    fig.tight_layout(); fig.savefig(IMG / "segments_bar.png", dpi=140); plt.close(fig)

    with open(MODELS / "kmeans_rfm.pkl", "wb") as f:
        pickle.dump({"model": km, "scaler": scaler, "labels": labels}, f)

    return {"summary": summary.to_dict(orient="records")}


# ---------------------------------------------------------------------
def main():
    print("Loading features from SQLite ...")
    df = load_feature_frame()
    print(f"  rows: {len(df):,}   churn rate: {df.churn_flag.mean():.2%}")

    print("Training churn model ...")
    churn = train_churn(df)
    print(f"  AUC={churn['roc_auc']}  Acc={churn['accuracy']}  AP={churn['avg_prec']}")

    print("Training review-score regressor ...")
    rev = train_review_regressor(df)
    print(f"  MAE={rev['mae']}  R2={rev['r2']}")

    print("Fitting KMeans customer segmentation ...")
    seg = segment_rfm(df)
    for row in seg["summary"]:
        print("  ", row)

    with open(ROOT / "ml" / "artifacts" / "metrics.json", "w") as f:
        json.dump({"churn": churn, "review": rev, "segments": seg}, f, indent=2, default=str)
    print("\nAll models trained.")


if __name__ == "__main__":
    main()
