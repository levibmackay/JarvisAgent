"""Meeting pipeline tests with a fake audio stream and fake STT."""

import wave
from pathlib import Path

import pytest

from jarvis.core.agent import Agent
from jarvis.meetings.recorder import MeetingRecorder
from jarvis.meetings.service import SUMMARY_PROMPT, MeetingService
from jarvis.tools.base import ToolRegistry
from jarvis.voice.base import STT, VoiceError
from tests.test_agent import FakeProvider
from tests.test_server import end_turn


class FakeStream:
    """Stands in for sounddevice.RawInputStream: emits audio on start()."""

    def __init__(self, callback, chunks: list[bytes]) -> None:
        self._callback = callback
        self._chunks = chunks

    def start(self) -> None:
        for chunk in self._chunks:
            self._callback(chunk, len(chunk) // 2, None, None)

    def stop(self) -> None: ...
    def close(self) -> None: ...


def make_recorder(chunks: list[bytes]) -> MeetingRecorder:
    return MeetingRecorder(
        stream_factory=lambda **kw: FakeStream(kw["callback"], chunks))


class FakeSTT(STT):
    def __init__(self, text: str) -> None:
        self.text = text
        self.transcribed: list[Path] = []

    def transcribe(self, wav_path: Path) -> str:
        self.transcribed.append(wav_path)
        return self.text


def test_recorder_writes_valid_wav(tmp_path) -> None:
    recorder = make_recorder([b"\x01\x02" * 100, b"\x03\x04" * 50])
    out = tmp_path / "m" / "audio.wav"
    recorder.start(out)
    recorder.stop()
    with wave.open(str(out)) as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16_000
        assert wav.getnframes() == 150


def test_recorder_rejects_empty_and_double_start(tmp_path) -> None:
    recorder = make_recorder([])
    recorder.start(tmp_path / "audio.wav")
    with pytest.raises(VoiceError, match="Already recording"):
        recorder.start(tmp_path / "other.wav")
    with pytest.raises(VoiceError, match="No audio"):
        recorder.stop()


def test_service_pipeline(tmp_path) -> None:
    stt = FakeSTT("we agreed to ship on friday")
    service = MeetingService(stt, tmp_path / "meetings")
    meeting_dir = service.new_meeting_dir()

    transcript = service.transcribe(meeting_dir)
    assert (meeting_dir / "transcript.txt").read_text() == transcript
    assert stt.transcribed == [meeting_dir / "audio.wav"]

    provider = FakeProvider([end_turn("## Summary\nShip friday.")])
    agent = Agent(provider, ToolRegistry(), "system")
    summary = service.summarize(meeting_dir, transcript, agent)
    assert (meeting_dir / "summary.md").read_text() == summary == "## Summary\nShip friday."
    # The summary prompt carried the transcript to the model.
    sent = provider.calls[0][-1]["content"]
    assert "we agreed to ship on friday" in sent
    assert sent.startswith(SUMMARY_PROMPT.split("{", 1)[0][:20])
