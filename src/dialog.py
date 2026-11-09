from __future__ import annotations

from typing import Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from .chains import history_prompt, state_prompt
from .journal import Journal
from .pipeline import PipelineResult, ProductSearchPipeline
from .schema import ProductQuery


# Задание 5.1. Состояние вне модели
class StateDialog:

    def __init__(self, llm, journal: Optional[Journal] = None,
                 prompt: ChatPromptTemplate = state_prompt):
        self.pipeline = ProductSearchPipeline(llm, prompt=prompt, journal=journal)
        self.state: Optional[ProductQuery] = None

    def send(self, text: str) -> PipelineResult:
        current = self.state.model_dump_json() if self.state else "нет (это первый запрос)"
        result = self.pipeline.invoke({"query": text, "current": current})
        if result.query is not None:
            self.state = result.query
        return result


# Задание 5.2. Сравнение с историей диалога
class HistoryDialog:

    def __init__(self, llm, journal: Optional[Journal] = None,
                 prompt: ChatPromptTemplate = history_prompt):
        self.pipeline = ProductSearchPipeline(llm, prompt=prompt, journal=journal)
        self.history: list[BaseMessage] = []

    @property
    def state(self) -> Optional[ProductQuery]:
        for m in reversed(self.history):
            if isinstance(m, AIMessage):
                try:
                    return ProductQuery.model_validate_json(m.content)
                except ValueError:
                    return None
        return None

    def send(self, text: str) -> PipelineResult:
        result = self.pipeline.invoke({"query": text, "history": list(self.history)})
        self.history.append(HumanMessage(text))
        self.history.append(AIMessage(
            result.query.model_dump_json() if result.query else (result.raw or "")))
        return result
