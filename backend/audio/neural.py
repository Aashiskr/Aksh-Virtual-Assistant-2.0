from __future__ import annotations

import asyncio
import os
import tempfile


class NeuralVoice:
    """Generates and plays one Edge neural speech utterance."""

    def __init__(
        self,
        voice: str = "hi-IN-MadhurNeural",
        rate: str = "+4%",
        pitch: str = "-8Hz",
        volume: str = "+8%",
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume

    def speak(self, text: str) -> None:
        path = self._temporary_mp3()
        try:
            asyncio.run(self._save(text, path))
            from playsound import playsound

            playsound(path)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    async def _save(self, text: str, path: str) -> None:
        import edge_tts

        communication = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
            volume=self.volume,
        )
        await communication.save(path)

    @staticmethod
    def _temporary_mp3() -> str:
        handle, path = tempfile.mkstemp(prefix="aksh-voice-", suffix=".mp3")
        os.close(handle)
        return path
