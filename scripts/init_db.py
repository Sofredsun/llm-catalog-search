import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db import init_db  # noqa: E402

path = init_db()
with sqlite3.connect(path) as conn:
    for cat, n, lo, hi in conn.execute(
        "SELECT category, COUNT(*), MIN(price),"
        "MAX(price) FROM products GROUP BY category"
    ):
        print(f"{cat:<11} {n:>2} шт.  {lo:>7} – {hi:>7} ₽")
print(f"База создана: {path}")
