from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["laptop", "smartphone", "tablet", "other"]
SortBy = Literal["price_asc", "price_desc"]

SUPPORTED_CATEGORIES: tuple[str, ...] = ("laptop", "smartphone", "tablet")


# Задание 2.1. Схема структурированного ответа
class ProductQuery(BaseModel):

    category: Category = Field(
        default="other",
        description=(
            "Категория товара: laptop (ноутбуки), smartphone (смартфоны, телефоны), "
            "tablet (планшеты). Любая другая категория (холодильники, наушники и т.п.) "
            "или если категория не указана — other."
        ),
    )
    max_price: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Верхняя граница цены в рублях, целое число без пробелов и единиц "
            "(«до 50 тысяч» → 50000, «дешевле 1,5 млн» → 1500000). "
            "null, если ограничение цены не указано."
        ),
    )
    sort_by: SortBy = Field(
        default="price_asc",
        description=(
            "Сортировка по цене: price_asc — сначала дешевые (по умолчанию), "
            "price_desc — сначала дорогие («самые дорогие», «топовые»)."
        ),
    )

    @property
    def is_supported(self) -> bool:
        return self.category in SUPPORTED_CATEGORIES
