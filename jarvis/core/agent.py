"""Agent turn engine: orchestrates LLM <-> tools until the model finishes."""

from typing import Any, Callable, Protocol

from jarvis.core.llm.base import LLMProvider, OnText
from jarvis.tools.base import ToolError

OnToolUse = Callable[[str, dict[str, Any]], None]
OnMessage = Callable[[dict[str, Any]], None]


class ToolExecutor(Protocol):
    """What the agent needs from the tool layer — satisfied by ToolRegistry
    (bare) and SafeExecutor (consent + audit)."""

    def schemas(self) -> list[dict[str, Any]]: ...
    def execute(self, name: str, params: dict[str, Any]) -> str: ...


class Agent:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolExecutor,
        system_prompt: str,
        max_tool_rounds: int = 25,
        on_message: OnMessage | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._system = system_prompt
        self._max_tool_rounds = max_tool_rounds
        self._on_message = on_message
        self._history: list[dict[str, Any]] = []

    def _append(self, message: dict[str, Any]) -> None:
        self._history.append(message)
        if self._on_message:
            self._on_message(message)

    def reset(self) -> None:
        self._history.clear()

    def run_turn(
        self,
        user_input: str,
        on_text: OnText,
        on_tool_use: OnToolUse | None = None,
    ) -> str:
        self._append({"role": "user", "content": user_input})

        for _ in range(self._max_tool_rounds):
            result = self._provider.stream_turn(
                system=self._system,
                messages=self._history,
                tools=self._registry.schemas(),
                on_text=on_text,
            )
            self._append({"role": "assistant", "content": result.raw_content})

            if result.stop_reason == "pause_turn":
                continue  # server-side pause; re-send to resume
            if result.stop_reason != "tool_use":
                return result.text

            tool_results: list[dict[str, Any]] = []
            for call in result.tool_calls:
                if on_tool_use:
                    on_tool_use(call.name, call.input)
                try:
                    output = self._registry.execute(call.name, call.input)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": call.id, "content": output}
                    )
                except ToolError as exc:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "content": f"Error: {exc}",
                            "is_error": True,
                        }
                    )
            self._append({"role": "user", "content": tool_results})

        raise RuntimeError(f"Exceeded {self._max_tool_rounds} tool rounds in a single turn")
