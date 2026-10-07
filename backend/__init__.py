"""Modern Aksh desktop assistant core."""

from .config import AkshSettings, load_settings

__all__ = ["AkshAssistant", "AkshSettings", "load_settings"]


def __getattr__(name: str):
    if name == "AkshAssistant":
        from .assistant import AkshAssistant

        return AkshAssistant
    raise AttributeError(name)
