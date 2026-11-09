from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda

from .db import UnsupportedCategoryError, search_products
from .schema import ProductQuery

# Часть 1. Базовая цепочка LangChain
CATEGORY_SYSTEM = (
    "Ты - ассистент интернет-магазина электроники. Определи, к какой категории "
    "товаров относится запрос покупателя (например: ноутбуки, смартфоны, планшеты "
    "или другое). Ответь одной короткой фразой. Язык ответа: {language}."
)

category_prompt = ChatPromptTemplate.from_messages(
    [("system", CATEGORY_SYSTEM), ("human", "{query}")]
)


def build_category_chain(llm):
    return category_prompt | llm | StrOutputParser()


# Часть 2. Structured Output и Pydantic
product_parser = PydanticOutputParser(pydantic_object=ProductQuery)

RULES = """Ты - модуль интерпретации запросов к каталогу интернет-магазина.
Твоя задача заключается в извлечении параметров поиска из запроса пользователя.
Не придумывай товары и не пиши SQL.

Правила:
- category: ноутбуки → laptop; смартфоны/телефоны → smartphone; планшеты → tablet;
любая другая категория товаров или категория не названа → other.
- max_price: верхняя граница цены в рублях целым числом.
«до 50 тысяч», «дешевле 50 000», «не дороже 50к» → 50000;
«1,5 млн» → 1500000. Если ограничения цены нет → null.
- sort_by: «самые дорогие», «сначала дорогие», «топовые» → price_desc;
«самые дешевые», «бюджетные» или ничего не сказано → price_asc.
- Ответ должен быть только JSON-объект по схеме ниже, без пояснений и без markdown."""

query_prompt = ChatPromptTemplate.from_messages(
    [("system", RULES + "\n\n{format_instructions}"), ("human", "{query}")]
).partial(format_instructions=product_parser.get_format_instructions())


def build_parse_chain(llm):
    return query_prompt | llm | product_parser


# Часть 3. Вызов классического программного обеспечения
def run_search(q: ProductQuery) -> dict:
    """Обычная функция: ProductQuery → результат поиска (используется в LCEL)."""
    try:
        products = search_products(q)
    except UnsupportedCategoryError:
        return {
            "query": q,
            "status": "unsupported",
            "products": [],
            "message": "Категория не поддерживается: "
                       "ищем только ноутбуки, смартфоны и планшеты.",
        }
    return {
        "query": q,
        "status": "ok" if products else "empty",
        "products": products,
        "message": f"Найдено товаров: {len(products)}" if products
        else "Подходящих товаров не найдено.",
    }


def build_search_chain(llm):
    return build_parse_chain(llm) | RunnableLambda(run_search, name="search_products")


# Часть 5. Уточняющие запросы
STATE_RULES = (
    RULES
    + """

Это продолжение диалога. Текущие параметры поиска (последний валидный запрос):
{current}

Обнови параметры с учетом новой реплики пользователя: меняй только то, о чем он говорит,
остальные значения оставь как есть. Если пользователь начинает совершенно новый поиск,
верни новые параметры."""
)

state_prompt = ChatPromptTemplate.from_messages(
    [("system", STATE_RULES + "\n\n{format_instructions}"), ("human", "{query}")]
).partial(format_instructions=product_parser.get_format_instructions())

HISTORY_RULES = (
    RULES
    + """

Это продолжение диалога: выше приведена его история (реплики пользователя и твои ответы-JSON).
Верни параметры поиска для последней реплики с учетом всей истории."""
)

history_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", HISTORY_RULES + "\n\n{format_instructions}"),
        MessagesPlaceholder("history"),
        ("human", "{query}"),
    ]
).partial(format_instructions=product_parser.get_format_instructions())


FOLLOWUP_RULES_V2 = """

Правила для уточняющих реплик (важнее правил по умолчанию выше):
- Значения по умолчанию (max_price = null, sort_by = price_asc) применяются только к первому запросу диалога.
  В уточнении параметр, о котором пользователь не говорит, сохраняет текущее значение.
- Смена категории («а что среди смартфонов?», «а если планшеты?», «а ноутбуки?») — это уточнение, а не новый поиск:
  меняй только category, а max_price и sort_by оставляй прежними.
- Сбрасывай ограничение цены только по явной просьбе: «без ограничения цены», «любой цены», «неважно сколько стоит».
- Начинай поиск с нуля только если пользователь прямо об этом говорит: «новый поиск», «начнем заново», «забудь прошлое».

Примеры (текущие параметры + реплика → результат):
- laptop, 80000, price_desc + «А что есть среди смартфонов?» → smartphone, 80000, price_desc
- tablet, 40000, price_asc + «А сначала дорогие?» → tablet, 40000, price_desc
- smartphone, 30000, price_desc + «А без ограничения по цене?» → smartphone, null, price_desc
- laptop, 70000, price_asc + «Новый поиск: планшеты» → tablet, null, price_asc"""

state_prompt_v2 = ChatPromptTemplate.from_messages(
    [("system", STATE_RULES + FOLLOWUP_RULES_V2 + "\n\n{format_instructions}"),
     ("human", "{query}")]
).partial(format_instructions=product_parser.get_format_instructions())

history_prompt_v2 = ChatPromptTemplate.from_messages(
    [
        ("system", HISTORY_RULES + FOLLOWUP_RULES_V2 + "\n\n{format_instructions}"),
        MessagesPlaceholder("history"),
        ("human", "{query}"),
    ]
).partial(format_instructions=product_parser.get_format_instructions())
