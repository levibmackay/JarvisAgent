"""Meeting pipeline: record → transcribe → summarize, artifacts on disk.

Each meeting gets a timestamped folder under ~/.jarvis/meetings with
audio.wav, transcript.txt, and summary.md. Transcription is local
(whisper.cpp); only the transcript text reaches the LLM for the summary.
"""

from datetime import datetime
from pathlib import Path

from jarvis.core.agent import Agent
from jarvis.voice.base import STT

SUMMARY_PROMPT = """\
Summarize this meeting transcript. Structure the summary as:
1. One-paragraph overview
2. Key decisions
3. Action items (owner if identifiable)
4. Open questions

Transcript:
---
{transcript}
---"""


class MeetingService:
    def __init__(self, stt: STT, meetings_dir: Path) -> None:
        self._stt = stt
        self._dir = meetings_dir.expanduser()

    def new_meeting_dir(self) -> Path:
        path = self._dir / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def audio_path(self, meeting_dir: Path) -> Path:
        return meeting_dir / "audio.wav"

    def transcribe(self, meeting_dir: Path) -> str:
        transcript = self._stt.transcribe(self.audio_path(meeting_dir))
        (meeting_dir / "transcript.txt").write_text(transcript)
        return transcript

    def summarize(self, meeting_dir: Path, transcript: str, agent: Agent) -> str:
        summary = agent.run_turn(
            SUMMARY_PROMPT.format(transcript=transcript), on_text=lambda _: None
        )
        (meeting_dir / "summary.md").write_text(summary)
        return summary
