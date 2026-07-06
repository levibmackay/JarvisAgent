"""Speech-to-text via whisper.cpp (local, private, fast on Apple Silicon)."""

import subprocess
from pathlib import Path

from jarvis.voice.base import STT, VoiceError

_MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"


class WhisperCppSTT(STT):
    def __init__(self, model_path: Path, binary: str = "whisper-cli",
                 timeout: float = 120.0) -> None:
        self._model = model_path.expanduser()
        self._binary = binary
        self._timeout = timeout

    def transcribe(self, wav_path: Path) -> str:
        if not self._model.is_file():
            raise VoiceError(
                f"Whisper model missing at {self._model}.\n"
                f"Download: curl -L --create-dirs -o {self._model} {_MODEL_URL}"
            )
        try:
            proc = subprocess.run(
                [
                    self._binary,
                    "-m", str(self._model),
                    "-f", str(wav_path),
                    "--no-prints",
                    "--no-timestamps",
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except FileNotFoundError:
            raise VoiceError(
                f"`{self._binary}` not found. Install with: brew install whisper-cpp"
            ) from None
        except subprocess.TimeoutExpired:
            raise VoiceError("Transcription timed out") from None
        if proc.returncode != 0:
            raise VoiceError(f"whisper failed: {proc.stderr.strip()[:300]}")
        return proc.stdout.strip()
