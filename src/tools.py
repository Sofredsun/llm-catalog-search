from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from pydantic import ValidationError

from .chains import run_search
from .journal import Journal
from .schema import ProductQuery

# Задание 3.4. Поиск как инструмент
@tool(
    "search_products",
    args_schema=ProductQuery,
    description=(
        "Поиск товаров в каталоге интернет-магазина электроники по категории "
        "(laptop, smartphone, tablet или other), максимальной цене в рублях и "
        "сортировке по цене. Вызывай для любого запроса покупателя о товарах."
    ),
)
def search_products_tool(category: str = "other", max_price: Optional[int] = None,
                         sort_by: str = "price_asc") -> list[dict]:
    return run_search(ProductQuery(category=category, max_price=max_price, sort_by=sort_by))["products"]


TOOL_SYSTEM = """Ты - модуль интерпретации запросов к каталогу интернет-магазина электроники.
Для поиска вызови инструмент search_products, передав параметры из запроса пользователя.
- category: ноутбуки → laptop; смартфоны/телефоны → smartphone; планшеты → tablet; иное → other.
- max_price: верхняя граница цены в рублях целым числом («до 50 тысяч» → 50000); если не указана — не передавай или null.
- sort_by: «самые дорогие»/«сначала дорогие» → price_desc, иначе price_asc."""

tool_prompt = ChatPromptTemplate.from_messages([("system", TOOL_SYSTEM), ("human", "{query}")])


@dataclass
class ToolResult:
    status: str  # ok | empty | unsupported | no_tool_call | invalid_args
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    query: Optional[ProductQuery] = None
    products: list[dict] = field(default_factory=list)
    message: str = ""


def run_tool_query(llm, query: str, journal: Optional[Journal] = None) -> ToolResult:
    journal = journal or Journal(echo=False)
    journal.log("request", query=query)
    journal.log("llm_call", attempt=1, mode="bind_tools")
    msg = (tool_prompt | llm.bind_tools([search_products_tool])).invoke({"query": query})
    calls = [{"name": c["name"], "args": c["args"]} for c in msg.tool_calls]
    journal.log("tool_calls", n=len(calls), calls=calls)

    calls = [c for c in calls if c["name"] == "search_products"]
    if not calls:
        journal.log("search_skipped", reason="no_tool_call")
        return ToolResult("no_tool_call", msg.content,
                          message="Модель не вызвала инструмент поиска.")

    try:
        q = ProductQuery.model_validate(calls[0]["args"])
    except ValidationError as e:
        journal.log("validate_reject", reason="invalid_args", errors=e.error_count())
        return ToolResult("invalid_args", msg.content, calls,
                          message=f"Некорректные аргументы: {e.errors()[0]['msg']}")

    journal.log("validate_ok", params=q.model_dump())
    if not q.is_supported:
        journal.log("search_skipped", reason="unsupported_category")
    else:
        journal.log("search_start", params=q.model_dump())
    res = run_search(q)
    if q.is_supported:
        journal.log("search_done", found=len(res["products"]))
    return ToolResult(res["status"], msg.content, calls, q,
                      res["products"], res["message"])
