from __future__ import annotations

import mimetypes
from pathlib import Path

import speech_recognition as sr

from ..config import AkshSettings
from .groq import GroqClient
from .script_normalizer import ScriptNormalizer


TRANSCRIPTION_PROMPT = (
    "Transcribe an Aksh assistant command exactly as spoken. The speaker may "
    "mix Hindi, Hinglish, and Indian English. Preserve Indian contact names "
    "and honorifics exactly, including distinctions such as Sudhir, Sudheer, "
    "and Sir. Preserve every phone-number digit exactly. Preserve app names, "
    "product names, numbers, WhatsApp, Flipkart, YouTube, and "
    "commands such as kholo, karo, bhejo, chalao, band, and confirm. Do not "
    "translate, answer, or expand the command. Always write in the Latin "
    "alphabet as Roman Hinglish or Indian English. Never use Urdu, Arabic, "
    "Perso-Arabic, or Devanagari script."
)


class GroqSpeechTranscriber:
    """High-accuracy shared speech-to-text for laptop and phone audio."""

    def __init__(self, settings: AkshSettings):
        self.settings = settings
        self.client = GroqClient(settings)
        self.script_normalizer = ScriptNormalizer(settings)

    @property
    def enabled(self) -> bool:
        return self.client.enabled

    def transcribe_audio(self, audio: sr.AudioData) -> str:
        content = audio.get_wav_data(convert_rate=16000, convert_width=2)
        return self._transcribe("command.wav", content, "audio/wav")

    def transcribe_path(self, path: Path) -> str:
        content_type = mimetypes.guess_type(path.name)[0] or "audio/mp4"
        return self._transcribe(path.name, path.read_bytes(), content_type)

    def _transcribe(
        self, filename: str, content: bytes, content_type: str
    ) -> str:
        response = self.client.post(
            "audio/transcriptions",
            files={"file": (filename, content, content_type)},
            data={
                "model": self.settings.groq_stt_model,
                "response_format": "json",
                "temperature": "0",
                "prompt": TRANSCRIPTION_PROMPT,
            },
            timeout=90,
        )
        response.raise_for_status()
        text = str(response.json().get("text", "")).strip()
        if not text:
            raise RuntimeError("Audio mein clear command nahi mili.")
        return self.script_normalizer.normalize(text)
