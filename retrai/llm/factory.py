"""LLM factory: returns a LangChain BaseChatModel backed by LiteLLM."""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel


@lru_cache(maxsize=32)
def get_llm(model_name: str = "claude-sonnet-4-6", temperature: float = 0.0) -> BaseChatModel:
    """Return a cached LangChain chat model via LiteLLM.

    Supports any model string that LiteLLM understands:
      - "claude-sonnet-4-6" / "claude-opus-4-6"
      - "gpt-4o" / "gpt-4o-mini"
      - "gemini/gemini-2.0-flash"
      - etc.
    """
    try:
        from langchain_litellm import ChatLiteLLM  # type: ignore[import-untyped]
    except ImportError:
        from langchain_community.chat_models import ChatLiteLLM  # type: ignore[no-redef]

    return ChatLiteLLM(model=model_name, temperature=temperature)  # type: ignore[return-value]
