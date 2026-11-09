from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger("catalog_search.pipeline")


# Задание 4.3. Журнал выполнения
def _redact(text: str) -> str:
    """Не допускает попадания токена в журнал, даже если он оказался в тексте."""
    key = os.getenv("LITELLM_API_KEY", "")
    if key and len(key) > 4 and key in text:
        text = text.replace(key, "***")
    return text


@dataclass
class Journal:
    echo: bool = True
    events: list[dict] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)

    def log(self, step: str, **data) -> None:
        event = {"t": round(time.perf_counter() - self._t0, 3), "step": step, **data}
        self.events.append(event)
        line = self.format_event(event)
        logger.info(line)
        if self.echo:
            print(line)

    @staticmethod
    def format_event(event: dict) -> str:
        details = " ".join(
            f"{k}={v if isinstance(v, (int, float)) else json.dumps(v, ensure_ascii=False)}"
            for k, v in event.items()
            if k not in ("t", "step")
        )
        return _redact(f"[{event['t']:7.3f}s] {event['step']:<14} {details}".rstrip())

    def steps(self) -> list[str]:
        return [e["step"] for e in self.events]

    def count(self, step: str) -> int:
        return sum(1 for e in self.events if e["step"] == step)

    def text(self) -> str:
        return "\n".join(self.format_event(e) for e in self.events)

    def clear(self) -> None:
        self.events.clear()
        self._t0 = time.perf_counter()
