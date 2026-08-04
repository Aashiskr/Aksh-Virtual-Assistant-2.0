from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    channels: int
    rate: int


def device_from_info(info: dict) -> AudioDevice:
    channels = max(1, min(2, int(info.get("maxInputChannels", 1))))
    return AudioDevice(
        index=int(info["index"]),
        name=str(info.get("name", "Unknown audio device")),
        channels=channels,
        rate=int(float(info.get("defaultSampleRate", 48000))),
    )


def pcm_level(pcm: bytes) -> float:
    samples = np.frombuffer(pcm, dtype=np.int16)
    if not samples.size:
        return 0.0
    normalized = samples.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(normalized * normalized)))


def wav_bytes(pcm: bytes, device: AudioDevice) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(device.channels)
        wav.setsampwidth(2)
        wav.setframerate(device.rate)
        wav.writeframes(pcm)
    return output.getvalue()
