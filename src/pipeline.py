from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from .chains import product_parser, query_prompt
from .db import search_products
from .journal import Journal
from .schema import ProductQuery

# Итоговый пайплайн с retry и журналом
@dataclass
class PipelineResult:
    status: str  # ok | empty | unsupported | cancelled | error
    query: Optional[ProductQuery]
    products: list[dict] = field(default_factory=list)
    message: str = ""
    attempts: int = 0
    usage: Optional[dict] = None
    raw: Optional[str] = None


def _short(text: str, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class ProductSearchPipeline:
    def __init__(
        self,
        llm,
        prompt: ChatPromptTemplate = query_prompt,
        journal: Optional[Journal] = None,
        max_attempts: int = 3,
        use_retry: bool = True,
        search_fn: Callable[[ProductQuery], list[dict]] = search_products,
        confirm: Optional[Callable[[ProductQuery], bool]] = None,
    ):
        self.llm = llm
        self.prompt = prompt
        self.journal = journal or Journal(echo=False)
        self.search_fn = search_fn
        self.confirm = confirm
        self.max_attempts = max_attempts if use_retry else 1
        self._attempt = 0
        self.last_usage: Optional[dict] = None
        self.last_raw: Optional[str] = None

        extract = RunnableLambda(self._generate_and_parse, name="generate_and_parse")
        if use_retry and max_attempts > 1:
            # Повтор только ошибок разбора/валидации ответа модели
            extract = extract.with_retry(
                stop_after_attempt=max_attempts,
                retry_if_exception_type=(OutputParserException,),
                wait_exponential_jitter=False,
            )
        self.extract = extract
        self.chain = (
            extract
            | RunnableLambda(self._validate, name="validate")
            | RunnableLambda(self._search, name="search")
        )

    # Стадии
    def _generate_and_parse(self, inputs: dict) -> ProductQuery:
        self._attempt += 1
        n = self._attempt
        self.journal.log("llm_call", attempt=n)
        msg = (self.prompt | self.llm).invoke(inputs)
        self.last_usage = getattr(msg, "usage_metadata", None)
        self.last_raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        try:
            q = product_parser.invoke(msg)
        except OutputParserException as e:
            cause = e.__cause__
            self.journal.log(
                "parse_error",
                attempt=n,
                error=type(cause).__name__ if cause else type(e).__name__,
                raw=_short(self.last_raw, 80),
            )
            raise
        self.journal.log("parse_ok", attempt=n, params=q.model_dump())
        return q

    def _validate(self, q: ProductQuery) -> ProductQuery:
        # Повторная проверка по схеме непосредственно перед обращением к БД
        q = ProductQuery.model_validate(q.model_dump())
        if q.is_supported:
            self.journal.log("validate_ok", category=q.category)
        else:
            self.journal.log("validate_reject", reason="unsupported_category",
                             category=q.category)
        return q

    def _search(self, q: ProductQuery) -> PipelineResult:
        if not q.is_supported:
            self.journal.log("search_skipped", reason="unsupported_category")
            return PipelineResult(
                "unsupported", q,
                message="Категория не поддерживается:"
                        "ищем только ноутбуки, смартфоны и планшеты.",
            )
        if q.max_price is None and self.confirm is not None:
            ok = bool(self.confirm(q))
            self.journal.log("confirm", question="поиск без ограничения цены", answer=ok)
            if not ok:
                return PipelineResult("cancelled", q,
                                      message="Поиск отменен пользователем.")
        self.journal.log("search_start", params=q.model_dump())
        products = self.search_fn(q)
        self.journal.log("search_done", found=len(products))
        if not products:
            return PipelineResult("empty", q, message="Подходящих товаров не найдено.")
        return PipelineResult("ok", q, products,
                              message=f"Найдено товаров: {len(products)}")

    # Вход
    def invoke(self, inputs: dict | str) -> PipelineResult:
        if isinstance(inputs, str):
            inputs = {"query": inputs}
        self._attempt = 0
        self.last_usage = self.last_raw = None
        self.journal.log("request", query=inputs.get("query", ""))
        try:
            result = self.chain.invoke(inputs)
        except OutputParserException:
            self.journal.log("failed", reason="parse_error", attempts=self._attempt)
            result = PipelineResult(
                "error", None,
                message=(
                    "Не удалось понять запрос: "
                    f"модель {self._attempt} раз(а) вернула ответ "
                    "в неверном формате. Попробуйте переформулировать."
                ),
            )
        except Exception as e:  # Сеть, авторизация и т.п. без трассировки и секретов
            self.journal.log("failed", reason=type(e).__name__)
            result = PipelineResult("error", None, message=f"Ошибка обращения к модели:"
                                                           f"{type(e).__name__}")
        result.attempts = self._attempt
        result.usage = self.last_usage
        result.raw = self.last_raw
        self.journal.log("result", status=result.status, found=len(result.products))
        return result
