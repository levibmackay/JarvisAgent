"""Voice interfaces — implementations are thin adapters over local binaries
so they can be swapped (e.g. different STT engines) without touching the CLI."""

from abc import ABC, abstractmethod
from pathlib import Path


class VoiceError(Exception):
    """Raised when a voice component is unavailable or fails."""


class TTS(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        """Speak text aloud; blocks until finished."""

    @abstractmethod
    def stop(self) -> None:
        """Stop any in-progress speech."""


class STT(ABC):
    @abstractmethod
    def transcribe(self, wav_path: Path) -> str:
        """Transcribe a 16 kHz mono WAV file to text."""
