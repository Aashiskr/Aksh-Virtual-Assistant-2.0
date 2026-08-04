from __future__ import annotations

from ..config import AkshSettings
from ..integrations.groq import GroqClient


def coach_english(settings: AkshSettings, sentence: str) -> str:
    sentence = sentence.strip()
    if not sentence:
        return "English practice ke liye ek sentence boliye; main gently correct karunga."
    if not settings.groq_api_key:
        return "English coaching ke liye Groq API key configured honi chahiye."
    response = GroqClient(settings).post(
        "chat/completions",
        json={
            "model": settings.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Aksh's friendly Indian English coach. Correct "
                        "the learner's sentence if needed, explain one key point, "
                        "then reply naturally. Use simple English and at most "
                        "three short sentences."
                    ),
                },
                {"role": "user", "content": sentence},
            ],
            "temperature": 0.2,
            "max_completion_tokens": 180,
        },
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["choices"][0]["message"]["content"]).strip()
