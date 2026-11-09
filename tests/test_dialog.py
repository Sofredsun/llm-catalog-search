"""Состояние хранится в программе, а не в модели."""
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.dialog import HistoryDialog, StateDialog

ANSWERS = [
    '{"category": "laptop", "max_price": 80000, "sort_by": "price_asc"}',
    '{"category": "laptop", "max_price": 80000, "sort_by": "price_desc"}',
    '{"category": "smartphone", "max_price": 80000, "sort_by": "price_desc"}',
]


def test_state_dialog_keeps_last_valid_query(db):
    d = StateDialog(FakeListChatModel(responses=ANSWERS))
    d.send("Покажи ноутбуки до 80 тысяч")
    d.send("А сначала дорогие?")
    assert d.state.sort_by == "price_desc" and d.state.max_price == 80000
    r = d.send("А что есть среди смартфонов?")
    assert d.state.category == "smartphone" and r.status == "ok"


def test_state_dialog_ignores_failed_turn(db):
    d = StateDialog(FakeListChatModel(responses=[ANSWERS[0], "oops", "oops", "oops"]))
    d.send("Покажи ноутбуки до 80 тысяч")
    r = d.send("???")
    assert r.status == "error" and d.state.category == "laptop"


def test_history_dialog_accumulates_messages(db):
    d = HistoryDialog(FakeListChatModel(responses=ANSWERS))
    for text in ("Покажи ноутбуки до 80 тысяч", "А сначала дорогие?",
                 "А что есть среди смартфонов?"):
        d.send(text)
    assert len(d.history) == 6 and d.state.category == "smartphone"
