"""Push-to-talk microphone capture to 16 kHz mono WAV.

sounddevice is imported lazily so the core app runs without the voice extra
installed (`pip install jarvis[voice]`).
"""

import tempfile
import wave
from pathlib import Path

from jarvis.voice.base import VoiceError

SAMPLE_RATE = 16_000


def record_push_to_talk() -> Path:
    """Record from the default mic until the user presses Enter."""
    try:
        import sounddevice as sd
    except ImportError:
        raise VoiceError(
            "sounddevice not installed. Install voice support: pip install 'jarvis[voice]'"
        ) from None

    chunks: list[bytes] = []

    def callback(indata, frames, time, status) -> None:
        chunks.append(bytes(indata))

    print("Recording… press Enter to stop.")
    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback
        ):
            input()
    except sd.PortAudioError as exc:
        raise VoiceError(f"Microphone unavailable: {exc}") from None

    if not chunks:
        raise VoiceError("No audio captured")

    wav_path = Path(tempfile.mkstemp(suffix=".wav", prefix="jarvis_")[1])
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(chunks))
    return wav_path
