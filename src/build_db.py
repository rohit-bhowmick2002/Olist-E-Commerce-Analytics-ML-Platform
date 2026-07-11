"""
Build SQLite database from Olist CSV files.
Creates indexes for query performance.
"""
import sqlite3
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "olist.db"

TABLES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_orders_customer ON orders(customer_id)",
    "CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(order_status)",
    "CREATE INDEX IF NOT EXISTS ix_orders_purchase ON orders(order_purchase_timestamp)",
    "CREATE INDEX IF NOT EXISTS ix_items_order ON order_items(order_id)",
    "CREATE INDEX IF NOT EXISTS ix_items_product ON order_items(product_id)",
    "CREATE INDEX IF NOT EXISTS ix_items_seller ON order_items(seller_id)",
    "CREATE INDEX IF NOT EXISTS ix_pay_order ON order_payments(order_id)",
    "CREATE INDEX IF NOT EXISTS ix_rev_order ON order_reviews(order_id)",
    "CREATE INDEX IF NOT EXISTS ix_cust_unique ON customers(customer_unique_id)",
    "CREATE INDEX IF NOT EXISTS ix_cust_state ON customers(customer_state)",
    "CREATE INDEX IF NOT EXISTS ix_prod_cat ON products(product_category_name)",
    "CREATE INDEX IF NOT EXISTS ix_sell_state ON sellers(seller_state)",
]


def build():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    total = 0
    for table, fname in TABLES.items():
        path = DATA_DIR / fname
        df = pd.read_csv(path)
        df.to_sql(table, conn, index=False, if_exists="replace")
        n = len(df)
        total += n
        print(f"  {table:22s} {n:>10,} rows")
    print(f"\n  TOTAL rows loaded: {total:,}")
    cur = conn.cursor()
    for stmt in INDEXES:
        cur.execute(stmt)
    conn.commit()
    conn.close()
    print(f"\n  Database written -> {DB_PATH}")


if __name__ == "__main__":
    build()
