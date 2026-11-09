from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_BASE_URL = "http://10.32.2.11:35000/v1"
DEFAULT_MODEL = "qwen3.8-27b"


def get_api_key() -> str:
    key = os.getenv("LITELLM_API_KEY", "").strip()
    if not key or key.startswith("<"):
        raise RuntimeError(
            "Не задан LITELLM_API_KEY. "
            "Скопируйте .env.example в .env и впишите свой токен."
        )
    return key


def make_llm(thinking: bool = False, temperature: float = 0.0, **kwargs):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=os.getenv("LITELLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=get_api_key(),
        model=os.getenv("MODEL_NAME", DEFAULT_MODEL),
        temperature=temperature,
        timeout=180,
        extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
        **kwargs,
    )
