"""Воспроизводимые тесты retry на фейковой модели."""
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.journal import Journal
from src.pipeline import ProductSearchPipeline

BAD = "Конечно! Вот что я нашел: {category: laptop}"
GOOD = '{"category": "laptop", "max_price": 70000, "sort_by": "price_asc"}'


class SpySearch:
    def __init__(self):
        self.calls = 0

    def __call__(self, q):
        self.calls += 1
        return [{"id": 1, "name": "Test laptop", "category": q.category, "price": 50000}]


def make(responses, use_retry=True):
    spy, journal = SpySearch(), Journal(echo=False)
    pipe = ProductSearchPipeline(FakeListChatModel(responses=responses), journal=journal,
                                 use_retry=use_retry, search_fn=spy)
    return pipe, spy, journal


def test_without_retry_fails_on_first_bad_answer():
    pipe, spy, journal = make([BAD, GOOD], use_retry=False)
    r = pipe.invoke("Найди ноутбуки дешевле 70 000 рублей")
    assert r.status == "error" and r.attempts == 1
    assert spy.calls == 0 and journal.count("search_start") == 0


def test_retry_recovers_on_second_attempt():
    pipe, spy, journal = make([BAD, GOOD])
    r = pipe.invoke("Найди ноутбуки дешевле 70 000 рублей")
    assert r.status == "ok" and r.attempts == 2
    assert journal.count("llm_call") == 2 and journal.count("parse_error") == 1
    assert spy.calls == 1
    steps = journal.steps()
    assert steps.index("search_start") > steps.index("validate_ok") > steps.index("parse_ok")


def test_retry_exhausted_after_three_attempts():
    pipe, spy, journal = make([BAD, BAD, BAD, GOOD])
    r = pipe.invoke("Найди ноутбуки дешевле 70 000 рублей")
    assert r.status == "error" and r.attempts == 3
    assert "3 раз" in r.message
    assert journal.count("llm_call") == 3 and spy.calls == 0
    assert journal.steps()[-2:] == ["failed", "result"]


def test_unsupported_category_skips_search():
    pipe, spy, journal = make(['{"category": "other"}'])
    r = pipe.invoke("Найди холодильники")
    assert r.status == "unsupported" and spy.calls == 0
    assert "search_skipped" in journal.steps()


def test_confirmation_before_search_without_price():
    spy, journal = SpySearch(), Journal(echo=False)
    pipe = ProductSearchPipeline(FakeListChatModel(responses=['{"category": "tablet"}']),
                                 journal=journal, search_fn=spy, confirm=lambda q: False)
    r = pipe.invoke("Хочу посмотреть планшеты")
    assert r.status == "cancelled" and spy.calls == 0 and "confirm" in journal.steps()


def test_journal_never_contains_token(monkeypatch):
    monkeypatch.setenv("LITELLM_API_KEY", "sk-secret-test-token")
    journal = Journal(echo=False)
    journal.log("request", query="ключ sk-secret-test-token")
    assert "sk-secret-test-token" not in journal.text()
