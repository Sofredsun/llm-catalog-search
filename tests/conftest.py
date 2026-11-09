import pytest

from src.db import init_db


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Отдельная тестовая база, чтобы тесты не зависели от data/catalog.db."""
    path = init_db(tmp_path / "test.db")
    monkeypatch.setattr("src.db.DB_PATH", path)
    import src.db as dbmod
    from src import chains, pipeline

    real = dbmod.search_products
    patched = lambda q, db_path=path: real(q, db_path)  # noqa: E731
    monkeypatch.setattr(chains, "search_products", patched)
    monkeypatch.setattr(pipeline, "search_products", patched)
    return path
