import math
import random
import unittest
from array import array

import speech_recognition as sr

from backend.audio import DoubleClapDetector


SAMPLE_RATE = 16_000


def synthetic_audio(
    clap_times: tuple[float, ...] = (),
    *,
    tone_times: tuple[float, ...] = (),
    duration: float = 1.6,
) -> sr.AudioData:
    samples = array("h", [0] * int(SAMPLE_RATE * duration))
    generator = random.Random(42)
    for clap_time in clap_times:
        start = int(clap_time * SAMPLE_RATE)
        for index in range(int(0.025 * SAMPLE_RATE)):
            envelope = max(0.0, 1.0 - index / (0.025 * SAMPLE_RATE))
            samples[start + index] = int(
                generator.randint(-15_000, 15_000) * envelope
            )
    for tone_time in tone_times:
        start = int(tone_time * SAMPLE_RATE)
        for index in range(int(0.07 * SAMPLE_RATE)):
            samples[start + index] = int(
                12_000 * math.sin(2 * math.pi * 220 * index / SAMPLE_RATE)
            )
    return sr.AudioData(samples.tobytes(), SAMPLE_RATE, 2)


class DoubleClapDetectorTests(unittest.TestCase):
    def stream_detected(self, detector, audio, chunk_samples=1024):
        raw = audio.get_raw_data(convert_width=2)
        chunk_bytes = chunk_samples * 2
        for start in range(0, len(raw), chunk_bytes):
            chunk = raw[start : start + chunk_bytes]
            observed_at = (start + len(chunk)) / 2 / SAMPLE_RATE
            if detector.detected_chunk(
                sr.AudioData(chunk, SAMPLE_RATE, 2),
                observed_at=observed_at,
            ):
                return True
        return False

    def test_streaming_chunks_trigger_without_speech_capture(self):
        detector = DoubleClapDetector()

        self.assertTrue(
            self.stream_detected(detector, synthetic_audio((0.45, 0.82)))
        )

    def test_streaming_tones_do_not_trigger(self):
        detector = DoubleClapDetector()

        self.assertFalse(
            self.stream_detected(
                detector,
                synthetic_audio(tone_times=(0.45, 0.82)),
            )
        )

    def test_two_clear_claps_trigger(self):
        detector = DoubleClapDetector()
        audio = synthetic_audio((0.45, 0.82))

        self.assertTrue(detector.detected(audio, observed_at=10.0))

    def test_single_clap_does_not_trigger(self):
        detector = DoubleClapDetector()

        self.assertFalse(
            detector.detected(synthetic_audio((0.45,)), observed_at=10.0)
        )

    def test_claps_outside_timing_window_do_not_trigger(self):
        detector = DoubleClapDetector()

        self.assertFalse(
            detector.detected(synthetic_audio((0.35, 1.30)), observed_at=10.0)
        )

    def test_loud_speech_like_tones_do_not_trigger(self):
        detector = DoubleClapDetector()

        self.assertFalse(
            detector.detected(
                synthetic_audio(tone_times=(0.45, 0.82)),
                observed_at=10.0,
            )
        )

    def test_cooldown_prevents_immediate_retrigger(self):
        detector = DoubleClapDetector()
        audio = synthetic_audio((0.45, 0.82))

        self.assertTrue(detector.detected(audio, observed_at=10.0))
        self.assertFalse(detector.detected(audio, observed_at=11.0))
        self.assertTrue(detector.detected(audio, observed_at=13.0))


if __name__ == "__main__":
    unittest.main()
