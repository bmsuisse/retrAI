"""Seed the DuckDB analytics database with sample data.

Run once:  python seed.py
"""

from __future__ import annotations

import duckdb


def seed() -> None:
    con = duckdb.connect("analytics.duckdb")

    con.execute("""
        CREATE OR REPLACE TABLE customers (
            customer_id   INTEGER PRIMARY KEY,
            name          VARCHAR,
            region        VARCHAR,
            signup_date   DATE,
            is_active     BOOLEAN
        )
    """)

    con.execute("""
        CREATE OR REPLACE TABLE orders (
            order_id      INTEGER PRIMARY KEY,
            customer_id   INTEGER REFERENCES customers(customer_id),
            product       VARCHAR,
            quantity       INTEGER,
            unit_price    DECIMAL(10, 2),
            order_date    DATE,
            status        VARCHAR
        )
    """)

    con.execute("""
        CREATE OR REPLACE TABLE products (
            product       VARCHAR PRIMARY KEY,
            category      VARCHAR,
            weight_kg     DECIMAL(5, 2)
        )
    """)

    # Populate customers
    con.execute("""
        INSERT INTO customers
        SELECT
            i AS customer_id,
            'Customer_' || i AS name,
            CASE i % 5
                WHEN 0 THEN 'EMEA'
                WHEN 1 THEN 'APAC'
                WHEN 2 THEN 'AMER'
                WHEN 3 THEN 'LATAM'
                ELSE 'EMEA'
            END AS region,
            DATE '2020-01-01' + INTERVAL (i % 1000) DAY AS signup_date,
            i % 7 != 0 AS is_active
        FROM generate_series(1, 50000) AS t(i)
    """)

    # Populate products
    products = [
        ("Widget A", "Electronics", 0.5),
        ("Widget B", "Electronics", 1.2),
        ("Gadget X", "Hardware", 3.0),
        ("Gadget Y", "Hardware", 2.5),
        ("Gizmo Z", "Accessories", 0.1),
    ]
    con.executemany(
        "INSERT INTO products VALUES (?, ?, ?)",
        products,
    )

    # Populate orders — 500k rows
    con.execute("""
        INSERT INTO orders
        SELECT
            i AS order_id,
            (i % 50000) + 1 AS customer_id,
            CASE i % 5
                WHEN 0 THEN 'Widget A'
                WHEN 1 THEN 'Widget B'
                WHEN 2 THEN 'Gadget X'
                WHEN 3 THEN 'Gadget Y'
                ELSE 'Gizmo Z'
            END AS product,
            (i % 10) + 1 AS quantity,
            ROUND(10.0 + (i % 90), 2) AS unit_price,
            DATE '2023-01-01' + INTERVAL (i % 365) DAY AS order_date,
            CASE i % 4
                WHEN 0 THEN 'shipped'
                WHEN 1 THEN 'delivered'
                WHEN 2 THEN 'pending'
                ELSE 'returned'
            END AS status
        FROM generate_series(1, 500000) AS t(i)
    """)

    con.close()
    print("✅  Seeded analytics.duckdb  (50k customers, 500k orders, 5 products)")


if __name__ == "__main__":
    seed()
