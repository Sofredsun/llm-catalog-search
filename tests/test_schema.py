"""Схема и невалидные ответы модели."""
import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from json import JSONDecodeError

from src.chains import product_parser
from src.schema import ProductQuery


def test_defaults():
    q = ProductQuery()
    assert (q.category, q.max_price, q.sort_by) == ("other", None, "price_asc")


def test_valid_json_roundtrip():
    q = product_parser.parse('{"category": "laptop",'
                             '"max_price": 70000,'
                             '"sort_by": "price_asc"}')
    assert isinstance(q, ProductQuery)
    assert ProductQuery.model_validate_json(q.model_dump_json()) == q


@pytest.mark.parametrize(
    "raw, cause",
    [
        ("{category: laptop, max_price: 70000}",
         JSONDecodeError),                                 # Синтаксически неверный JSON
        ("Конечно! Вот ноутбуки до 70 000 ₽: Acer Aspire 3",
         JSONDecodeError),                                 # Текст вместо JSON
        ('{"category": "phone", "max_price": 30000}',
         ValidationError),                                 # Вне перечисления
        ('{"category": "laptop", "max_price": "дорого"}',
         ValidationError),                                 # Неверный тип
        ('{"category": "laptop", "max_price": -5}',
         ValidationError),                                 # Нарушение ge=0
        ('{"category": "laptop", "sort_by": "cheap"}',
         ValidationError),                                 # Вне перечисления
    ],
)
def test_invalid_outputs_raise(raw, cause):
    with pytest.raises(OutputParserException) as exc:
        product_parser.parse(raw)
    assert isinstance(exc.value.__cause__, cause)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"category": "laptop",'
         '"max_price": 70000', 70000),          # Незакрытая скобка: парсер достраивает
        ('{"category": "laptop",'
         '"max_price": "50000"}', 50000),       # Строка-число приводится к int
        ('```json\n{"category": "laptop",'
         '"max_price": 50000.0}\n```', 50000),  # markdown и 50000.0
    ],
)
def test_parser_is_lenient(raw, expected):
    """Эти "ошибки" НЕ вызывают исключения"""
    assert product_parser.parse(raw).max_price == expected
