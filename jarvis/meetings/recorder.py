"""Long-form audio capture to disk (meetings run hours — never buffer in RAM).

The input device is chosen by name substring ("BlackHole" picks the
loopback driver); None means the default microphone.
"""

import threading
import wave
from pathlib import Path
from typing import Any, Callable

from jarvis.voice.base import VoiceError

SAMPLE_RATE = 16_000  # what whisper.cpp expects

StreamFactory = Callable[..., Any]  # returns a started sounddevice-like stream


def _default_stream_factory(**kwargs: Any) -> Any:
    try:
        import sounddevice as sd
    except ImportError:
        raise VoiceError(
            "sounddevice not installed. Install voice support: pip install 'jarvis[voice]'"
        ) from None
    try:
        return sd.RawInputStream(**kwargs)
    except sd.PortAudioError as exc:
        raise VoiceError(f"Audio device unavailable: {exc}") from None


def resolve_device(name_fragment: str | None) -> int | str | None:
    """Map a device-name fragment to a sounddevice input device index.
    None or empty means the default microphone."""
    if not name_fragment:
        return None
    import sounddevice as sd

    for index, info in enumerate(sd.query_devices()):
        if name_fragment.lower() in info["name"].lower() and info["max_input_channels"] > 0:
            return index
    raise VoiceError(
        f"No input device matching {name_fragment!r}. For system audio: "
        "brew install blackhole-2ch, then create a Multi-Output Device in "
        "Audio MIDI Setup."
    )


class MeetingRecorder:
    def __init__(self, device: int | str | None = None,
                 stream_factory: StreamFactory = _default_stream_factory) -> None:
        self._device = device
        self._stream_factory = stream_factory
        self._stream: Any = None
        self._wav: wave.Wave_write | None = None
        self._write_lock = threading.Lock()
        self.frames_written = 0

    def start(self, out_path: Path) -> None:
        if self._stream is not None:
            raise VoiceError("Already recording")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._wav = wave.open(str(out_path), "wb")
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)
        self._wav.setframerate(SAMPLE_RATE)
        self._stream = self._stream_factory(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16",
            device=self._device, callback=self._on_audio,
        )
        self._stream.start()

    def _on_audio(self, indata: Any, frames: int, time: Any, status: Any) -> None:
        with self._write_lock:
            if self._wav is not None:
                self._wav.writeframes(bytes(indata))
                self.frames_written += frames

    def stop(self) -> None:
        if self._stream is None:
            raise VoiceError("Not recording")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._write_lock:
            assert self._wav is not None
            self._wav.close()
            self._wav = None
        if self.frames_written == 0:
            raise VoiceError("No audio captured")
