"""Text-to-speech via macOS `say` — zero dependencies, always available."""

import subprocess

from jarvis.voice.base import TTS, VoiceError


class MacSayTTS(TTS):
    def __init__(self, voice: str | None = None, rate: int | None = None) -> None:
        self._voice = voice
        self._rate = rate
        self._proc: subprocess.Popen | None = None

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        argv = ["say"]
        if self._voice:
            argv += ["-v", self._voice]
        if self._rate:
            argv += ["-r", str(self._rate)]
        try:
            self._proc = subprocess.Popen(argv, stdin=subprocess.PIPE)
            assert self._proc.stdin is not None
            self._proc.stdin.write(text.encode())
            self._proc.stdin.close()
            self._proc.wait()
        except FileNotFoundError:
            raise VoiceError("`say` not found — is this macOS?") from None
        finally:
            self._proc = None

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
