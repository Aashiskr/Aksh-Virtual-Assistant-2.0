import tempfile
import unittest
from pathlib import Path

import numpy as np
import speech_recognition as sr

from backend.audio.voiceprint import VoicePrintManager


def synthetic_voice(frequency: float, phase: float = 0.0) -> sr.AudioData:
    sample_rate = 16000
    duration = 1.4
    axis = np.arange(int(sample_rate * duration)) / sample_rate
    envelope = np.minimum(1.0, axis * 8) * np.minimum(1.0, (duration - axis) * 8)
    waveform = (
        np.sin(2 * np.pi * frequency * axis + phase)
        + 0.45 * np.sin(2 * np.pi * frequency * 2.1 * axis)
        + 0.2 * np.sin(2 * np.pi * frequency * 3.2 * axis)
    )
    pcm = np.clip(waveform * envelope * 9000, -32767, 32767).astype(np.int16)
    return sr.AudioData(pcm.tobytes(), sample_rate, 2)


class VoicePrintTests(unittest.TestCase):
    def test_enrollment_and_local_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "voice.dat"
            manager = VoicePrintManager(profile, threshold=0.70)
            manager.enroll(
                [
                    synthetic_voice(175, 0.0),
                    synthetic_voice(177, 0.2),
                    synthetic_voice(173, 0.4),
                ]
            )
            matched, good_score = manager.verify(synthetic_voice(176, 0.1))
            _, different_score = manager.verify(synthetic_voice(340, 0.1))
            self.assertTrue(profile.exists())
            self.assertTrue(matched)
            self.assertGreater(good_score, different_score)


if __name__ == "__main__":
    unittest.main()
