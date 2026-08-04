from __future__ import annotations

from ..config import AkshSettings
from ..integrations.groq import GroqClient
from ..integrations.script_normalizer import ScriptNormalizer


class MeetingTranscriber:
    def __init__(self, settings: AkshSettings):
        self.settings = settings
        self.client = GroqClient(settings)
        self.script_normalizer = ScriptNormalizer(settings)

    def transcribe(self, wav_data: bytes, source: str) -> str:
        label = "the user" if source == "owner" else "a meeting participant"
        prompt = (
            f"Transcribe one complete spoken turn from {label}. The meeting may "
            "mix Hindi, Hinglish, and Indian English. Preserve technical terms, "
            "names, and every number exactly. Use Latin-script Roman Hinglish or "
            "Indian English, never Urdu/Arabic script. Do not answer, summarize, "
            "or add words."
        )
        response = self.client.post(
            "audio/transcriptions",
            files={"file": (f"{source}.wav", wav_data, "audio/wav")},
            data={
                "model": self.settings.groq_stt_model,
                "response_format": "json",
                "temperature": "0",
                "prompt": prompt,
            },
            timeout=90,
        )
        response.raise_for_status()
        text = str(response.json().get("text", "")).strip()
        return self.script_normalizer.normalize(text) if text else ""
