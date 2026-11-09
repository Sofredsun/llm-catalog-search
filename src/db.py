from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import PROJECT_ROOT
from .schema import SUPPORTED_CATEGORIES, ProductQuery

# Задание 3.1. Каталог товаров и Задание 3.2. Программный поиск
DB_PATH = PROJECT_ROOT / "data" / "catalog.db"

PRODUCTS: list[tuple[str, str, int]] = [
    # Ноутбуки
    ("HONOR MagicBook X16 AMD 2025", "laptop", 70299),
    ("MSI Katana 17 B13UCR-1491XRU", "laptop", 99299),
    ("Tecno Megabook K15SDA", "laptop", 55299),
    ("DEXP Atlas A15-I3W400", "laptop", 44299),
    ("ASUS TUF Gaming FX707VJB-HX098", "laptop", 97299),
    ("Apple MacBook Air M5", "laptop", 143999),
    # Смартфоны
    ("Apple iPhone 17", "smartphone", 88790),
    ("Xiaomi REDMI Note 15 Pro", "smartphone", 24299),
    ("HONOR 600", "smartphone", 59999),
    ("Samsung Galaxy A57", "smartphone", 41999),
    ("POCO X8 Pro Max", "smartphone", 58799),
    # Планшеты
    ("Apple iPad (11th Gen)", "tablet", 45999),
    ("Xiaomi REDMI Pad 2 LTE", "tablet", 27999),
    ("HUAWEI MatePad SE 11 Wi-Fi", "tablet", 24999),
    ("HONOR Pad X9a LTE", "tablet", 30999),
    # Прочее
    ("SteelSeries Arctis Nova 1", "other", 7299),
]

ALLOWED_SORT = {"price_asc": "ASC", "price_desc": "DESC"}


class UnsupportedCategoryError(ValueError):
    """Категория other: поиск по всему каталогу намеренно не выполняется."""


def init_db(path: Path | str = DB_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS products;
            CREATE TABLE products (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL,
                category TEXT    NOT NULL,
                price    INTEGER NOT NULL CHECK (price >= 0)
            );
            """
        )
        conn.executemany(
            "INSERT INTO products (name, category, price) VALUES (?, ?, ?)", PRODUCTS
        )
    return path


def build_sql(q: ProductQuery) -> tuple[str, list]:
    if q.category not in SUPPORTED_CATEGORIES:
        raise UnsupportedCategoryError(q.category)
    where = ["category = ?"]
    params: list = [q.category]
    if q.max_price is not None:
        where.append("price <= ?")
        params.append(q.max_price)
    order = ALLOWED_SORT[q.sort_by]
    sql = (
        "SELECT id, name, category, price FROM products "
        f"WHERE {' AND '.join(where)} ORDER BY price {order}, id"
    )
    return sql, params


def search_products(q: ProductQuery, db_path: Path | str = DB_PATH) -> list[dict]:
    """
    Возвращает список товаров, подходящих под запрос.

    Для category='other' выбрасывает UnsupportedCategoryError: интерфейс сообщает
    о неподдерживаемой категории вместо поиска по всему каталогу.
    """
    if not isinstance(q, ProductQuery):
        q = ProductQuery.model_validate(q)
    sql, params = build_sql(q)
    if not Path(db_path).exists():
        init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def format_products(products: list[dict]) -> str:
    if not products:
        return "—"
    return "; ".join(f"{p['name']} ({p['price']:,} ₽)".replace(",", " ")
                     for p in products)
