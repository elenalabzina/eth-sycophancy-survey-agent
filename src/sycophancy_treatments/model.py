from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from openai import OpenAI
import yaml


@dataclass(frozen=True)
class ModelConfig:
    model: str
    api_key_env: str | None = "OPENAI_API_KEY"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float | None = 0.4
    top_p: float | None = 1.0
    max_tokens: int = 700
    token_limit_parameter: str = "max_tokens"
    disable_thinking: bool = False

    @classmethod
    def from_yaml(cls, path: str) -> "ModelConfig":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls(**raw)


class ChatModel:
    """Minimal OpenAI-compatible chat client."""

    def __init__(self, config: ModelConfig):
        self.config = config
        api_key = config.api_key
        if api_key is None and config.api_key_env:
            api_key = os.environ.get(config.api_key_env)
        if not api_key:
            source = config.api_key_env or "config.api_key"
            raise RuntimeError(f"Missing API key from {source}")

        kwargs: dict[str, Any] = {"api_key": api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self.client = OpenAI(**kwargs)

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        token_limit = self.config.max_tokens if max_tokens is None else max_tokens

        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
        }

        effective_temperature = (
            self.config.temperature if temperature is None else temperature
        )
        if effective_temperature is not None:
            request["temperature"] = effective_temperature
        if self.config.top_p is not None:
            request["top_p"] = self.config.top_p

        if self.config.token_limit_parameter not in {"max_tokens", "max_completion_tokens"}:
            raise ValueError(
                "token_limit_parameter must be 'max_tokens' or 'max_completion_tokens'"
            )
        request[self.config.token_limit_parameter] = token_limit

        if self.config.disable_thinking:
            request["extra_body"] = {
                "chat_template_kwargs": {
                    "enable_thinking": False,
                }
            }

        response = self.client.chat.completions.create(**request)
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Model returned an empty response.")
        return content.strip()
