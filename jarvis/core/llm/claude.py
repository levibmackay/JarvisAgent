"""Claude API provider (primary brain)."""

from typing import Any

import anthropic

from jarvis.core.llm.base import LLMProvider, OnText, ToolCall, TurnResult


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str, max_tokens: int) -> None:
        # Credentials resolve from ANTHROPIC_API_KEY or an `ant auth login` profile.
        self._client = anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    def stream_turn(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        on_text: OnText,
    ) -> TurnResult:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
            "thinking": {"type": "adaptive"},
        }
        if tools:
            kwargs["tools"] = tools

        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                on_text(text)
            final = stream.get_final_message()

        return TurnResult(
            text="".join(b.text for b in final.content if b.type == "text"),
            stop_reason=final.stop_reason or "end_turn",
            tool_calls=[
                ToolCall(id=b.id, name=b.name, input=b.input)
                for b in final.content
                if b.type == "tool_use"
            ],
            raw_content=final.content,
        )
