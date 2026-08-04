from __future__ import annotations

import random
import urllib.parse
import webbrowser
from datetime import datetime


MOOD_TERMS = {
    "sad": (
        "sad",
        "lonely",
        "depressed",
        "cry",
        "mood off",
        "dukhi",
        "udaas",
        "akela",
    ),
    "angry": (
        "angry",
        "furious",
        "annoyed",
        "gussa",
        "irritated",
        "pareshan",
    ),
    "happy": (
        "happy",
        "amazing",
        "excited",
        "great",
        "khush",
        "mast",
        "awesome",
    ),
}

MOOD_MEDIA = {
    "sad": (
        "soothing Hindi music for a difficult day",
        "gentle Hindi motivation songs",
    ),
    "angry": (
        "10 minute meditation for anger",
        "calming Indian flute music",
    ),
    "happy": (
        "upbeat Hindi happy songs",
        "Punjabi high energy dance mix",
    ),
    "neutral": ("relaxing Hindi lofi music",),
}

TIME_MEDIA = {
    "morning": (
        "morning bhajans Hindi",
        "positive morning affirmations India",
        "morning workout music",
    ),
    "afternoon": (
        "instrumental focus music",
        "soft Bollywood acoustic songs",
        "productivity talk Hindi",
    ),
    "evening": (
        "latest Punjabi party songs",
        "Hindi standup comedy",
        "Coke Studio India songs",
    ),
    "night": (
        "guided sleep meditation Hindi",
        "old Hindi songs Kishore Kumar",
        "rain sounds for sleeping",
    ),
}


def detect_mood(text: str) -> str:
    normalized = text.casefold()
    scores = {
        mood: sum(term in normalized for term in terms)
        for mood, terms in MOOD_TERMS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "neutral"


def mood_support(text: str) -> str:
    mood = detect_mood(text)
    query = random.choice(MOOD_MEDIA[mood])
    _open_youtube_search(query)
    messages = {
        "sad": "Main yahin hoon. Thoda soothing music chala raha hoon; baat karni ho to bolo.",
        "angry": "Lag raha hai tension zyada hai. Ek calming track chala raha hoon—pehle ek slow breath.",
        "happy": "Nice! Is energy ko aur achha rakhte hain—happy music chala raha hoon.",
        "neutral": "Mood clear nahi hua, isliye halka relaxing music chala raha hoon.",
    }
    return messages[mood]


def time_dj(now: datetime | None = None) -> str:
    hour = (now or datetime.now()).hour
    if 5 <= hour < 12:
        period, message = "morning", "Good morning! Day ko achhi energy se start karte hain."
    elif 12 <= hour < 17:
        period, message = "afternoon", "Focus ke liye ek calm afternoon pick chala raha hoon."
    elif 17 <= hour < 21:
        period, message = "evening", "Good evening! Thoda fresh mood banate hain."
    else:
        period, message = "night", "Raat ho gayi hai; kuch relaxing chala raha hoon."
    _open_youtube_search(random.choice(TIME_MEDIA[period]))
    return message


def _open_youtube_search(query: str) -> None:
    webbrowser.open(
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote_plus(query)
    )
