import subprocess
from pathlib import Path

import pytest

from jarvis.voice.base import VoiceError
from jarvis.voice.stt import WhisperCppSTT
from jarvis.voice.tts import MacSayTTS


class FakeProc:
    def __init__(self):
        self.stdin = self
        self.written = b""
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written += data

    def close(self) -> None:
        self.closed = True

    def wait(self) -> int:
        return 0

    def poll(self):
        return 0


def test_tts_builds_say_command(monkeypatch) -> None:
    captured: dict = {}

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    MacSayTTS(voice="Samantha", rate=200).speak("hello")
    assert captured["argv"] == ["say", "-v", "Samantha", "-r", "200"]


def test_tts_skips_empty_text(monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: pytest.fail("say should not be spawned for empty text"),
    )
    MacSayTTS().speak("   ")


def test_stt_missing_model(tmp_path: Path) -> None:
    stt = WhisperCppSTT(tmp_path / "missing.bin")
    with pytest.raises(VoiceError, match="Download"):
        stt.transcribe(tmp_path / "audio.wav")


def test_stt_transcribes(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake")

    def fake_run(argv, **kwargs):
        assert argv[0] == "whisper-cli" and "--no-timestamps" in argv
        return subprocess.CompletedProcess(argv, 0, stdout="  hello world \n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert WhisperCppSTT(model).transcribe(tmp_path / "a.wav") == "hello world"


def test_stt_missing_binary(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake")

    def fake_run(argv, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(VoiceError, match="brew install whisper-cpp"):
        WhisperCppSTT(model).transcribe(tmp_path / "a.wav")


def test_stt_failure_surfaces_stderr(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake")

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="bad wav header")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(VoiceError, match="bad wav header"):
        WhisperCppSTT(model).transcribe(tmp_path / "a.wav")
