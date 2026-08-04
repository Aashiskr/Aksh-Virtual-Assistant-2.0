from __future__ import annotations

import io
import json
import logging
import time
import wave
from pathlib import Path
from typing import Iterable

import numpy as np
import speech_recognition as sr

from .features import speaker_embedding


LOGGER = logging.getLogger(__name__)


class VoicePrintManager:
    """Creates and verifies the owner's local DPAPI-protected voice profile."""

    def __init__(self, profile_path: Path, threshold: float = 0.72):
        self.profile_path = profile_path
        self.threshold = threshold
        self._profile: np.ndarray | None = None
        self._load()

    @property
    def enrolled(self) -> bool:
        return self._profile is not None

    def enroll(self, audio_samples: Iterable[sr.AudioData]) -> int:
        embeddings = [self.embedding_from_audio(audio) for audio in audio_samples]
        if len(embeddings) < 3:
            raise ValueError("At least three clear voice samples are required.")
        profile = np.vstack(embeddings).mean(axis=0)
        profile /= np.linalg.norm(profile) + 1e-9
        self._profile = profile.astype(np.float32)
        self._save(len(embeddings))
        return len(embeddings)

    def verify(self, audio: sr.AudioData) -> tuple[bool, float]:
        if self._profile is None:
            return False, 0.0
        try:
            current = self.embedding_from_audio(audio)
        except Exception as exc:
            LOGGER.debug("Voiceprint extraction failed: %s", exc)
            return False, 0.0
        score = float(np.dot(self._profile, current))
        return score >= self.threshold, score

    @staticmethod
    def embedding_from_audio(audio: sr.AudioData) -> np.ndarray:
        wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
        with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            frames = wav_file.readframes(wav_file.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
        if sample_rate != 16000 and samples.size:
            duration = samples.size / sample_rate
            old_axis = np.linspace(0.0, duration, samples.size, endpoint=False)
            new_axis = np.linspace(
                0.0, duration, max(1, int(duration * 16000)), endpoint=False
            )
            samples = np.interp(new_axis, old_axis, samples)
            sample_rate = 16000
        return speaker_embedding(samples, sample_rate)

    def _save(self, sample_count: int) -> None:
        if self._profile is None:
            return
        payload = json.dumps(
            {
                "version": 1,
                "sample_count": sample_count,
                "embedding": self._profile.tolist(),
                "saved_at": time.time(),
            }
        ).encode("utf-8")
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.profile_path.with_suffix(".tmp")
        temporary.write_bytes(self._protect(payload))
        temporary.replace(self.profile_path)

    def _load(self) -> None:
        if not self.profile_path.exists():
            return
        try:
            data = self._unprotect(self.profile_path.read_bytes())
            payload = json.loads(data.decode("utf-8"))
            embedding = np.asarray(payload["embedding"], dtype=np.float32)
            if embedding.ndim == 1 and embedding.size > 20:
                embedding /= np.linalg.norm(embedding) + 1e-9
                self._profile = embedding
        except Exception as exc:
            LOGGER.warning("Owner voice profile could not be loaded: %s", exc)

    @staticmethod
    def _protect(data: bytes) -> bytes:
        try:
            import win32crypt

            protected = win32crypt.CryptProtectData(
                data, "Aksh owner voiceprint", None, None, None, 0
            )
            return protected[1] if isinstance(protected, tuple) else protected
        except Exception:
            return b"AKSH-PLAIN\x00" + data

    @staticmethod
    def _unprotect(data: bytes) -> bytes:
        if data.startswith(b"AKSH-PLAIN\x00"):
            return data[len(b"AKSH-PLAIN\x00") :]
        import win32crypt

        return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
