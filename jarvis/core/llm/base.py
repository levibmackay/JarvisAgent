"""Provider-agnostic LLM interface.

Local models (Ollama/MLX) plug in later by implementing LLMProvider —
the agent loop never imports a vendor SDK directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class TurnResult:
    text: str
    stop_reason: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Provider-native content blocks, echoed back into history verbatim
    # (preserves thinking blocks, tool_use blocks, signatures).
    raw_content: Any = None


OnText = Callable[[str], None]


class LLMProvider(ABC):
    @abstractmethod
    def stream_turn(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        on_text: OnText,
    ) -> TurnResult:
        """Run one model turn, streaming text chunks to on_text."""
