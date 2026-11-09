"""Каталог и детерминированный поиск."""
import sqlite3

import pytest

from src.db import UnsupportedCategoryError, build_sql, search_products
from src.schema import ProductQuery


def test_catalog_size(db):
    with sqlite3.connect(db) as conn:
        counts = dict(conn.execute("SELECT category,"
                                   "COUNT(*) FROM products GROUP BY category"))
    assert sum(counts.values()) >= 15
    assert all(counts[c] >= 4 for c in ("laptop", "smartphone", "tablet"))


def test_filter_and_sort_asc(db):
    res = search_products(ProductQuery(category="laptop", max_price=70000), db)
    assert [p["price"] for p in res] == sorted(p["price"] for p in res)
    assert res and all(p["category"] == "laptop" and p["price"] <= 70000 for p in res)


def test_sort_desc(db):
    res = search_products(ProductQuery(category="smartphone", sort_by="price_desc"), db)
    prices = [p["price"] for p in res]
    assert prices == sorted(prices, reverse=True) and len(prices) == 5


def test_empty_result(db):
    assert search_products(ProductQuery(category="laptop", max_price=30000), db) == []


def test_other_is_not_searched(db):
    with pytest.raises(UnsupportedCategoryError):
        search_products(ProductQuery(category="other"), db)


def test_sql_is_parameterized():
    sql, params = build_sql(ProductQuery(category="tablet", max_price=40000, sort_by="price_desc"))
    assert "?" in sql and "40000" not in sql and "tablet" not in sql
    assert params == ["tablet", 40000]
    assert sql.endswith("ORDER BY price DESC, id")
