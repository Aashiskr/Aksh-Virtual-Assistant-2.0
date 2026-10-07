from __future__ import annotations

import math
import statistics
import sys
import time
from array import array

import speech_recognition as sr


class DoubleClapDetector:
    """Detect two short, sharp audio transients without transcribing audio."""

    def __init__(
        self,
        *,
        minimum_gap_seconds: float = 0.12,
        maximum_gap_seconds: float = 0.70,
        cooldown_seconds: float = 2.0,
    ) -> None:
        self.minimum_gap_seconds = minimum_gap_seconds
        self.maximum_gap_seconds = maximum_gap_seconds
        self.cooldown_seconds = cooldown_seconds
        self._pending_clap_at: float | None = None
        self._last_trigger_at = float("-inf")
        self._stream_noise_floor: float | None = None
        self._stream_event_active = False

    def detected(
        self,
        audio: sr.AudioData,
        *,
        observed_at: float | None = None,
    ) -> bool:
        """Return True once when a valid clap pair is present in captured audio."""

        now = time.monotonic() if observed_at is None else observed_at
        offsets, duration = self._clap_offsets(audio)
        capture_started_at = now - duration

        for offset in offsets:
            clap_at = capture_started_at + offset
            if self._register_clap(clap_at):
                return True

        if (
            self._pending_clap_at is not None
            and now - self._pending_clap_at > self.maximum_gap_seconds
        ):
            self._pending_clap_at = None
        return False

    def reset_stream(self) -> None:
        self._pending_clap_at = None
        self._stream_noise_floor = None
        self._stream_event_active = False

    def detected_chunk(
        self,
        audio: sr.AudioData,
        *,
        observed_at: float | None = None,
    ) -> bool:
        """Process one continuous PCM chunk and retain state across chunks."""

        now = time.monotonic() if observed_at is None else observed_at
        raw = audio.get_raw_data(convert_width=2)
        samples = array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if sys.byteorder != "little":
            samples.byteswap()
        if len(samples) < 2:
            return False

        signal_energy = sum(int(value) * int(value) for value in samples)
        signal_rms = math.sqrt(signal_energy / len(samples))
        signal_peak = max(abs(int(value)) for value in samples)
        difference_energy = sum(
            (int(samples[index]) - int(samples[index - 1])) ** 2
            for index in range(1, len(samples))
        )
        difference_rms = math.sqrt(difference_energy / (len(samples) - 1))
        roughness = difference_rms / max(1.0, signal_rms)
        crest_factor = signal_peak / max(1.0, signal_rms)

        if self._stream_noise_floor is None:
            self._stream_noise_floor = max(1.0, signal_rms)
            return False
        noise_floor = max(1.0, self._stream_noise_floor)
        rms_threshold = max(90.0, noise_floor * 3.5)
        peak_threshold = max(350.0, noise_floor * 6.0)
        impulsive = (
            signal_rms >= rms_threshold
            and signal_peak >= peak_threshold
            and roughness >= 0.30
            and crest_factor >= 1.25
        )

        if impulsive:
            if self._stream_event_active:
                return False
            self._stream_event_active = True
            return self._register_clap(now)

        self._stream_event_active = False
        # Adapt slowly to fans and room noise, but never learn a sharp event as
        # the new baseline.
        self._stream_noise_floor = (noise_floor * 0.97) + (signal_rms * 0.03)
        if self._pending_clap_at is not None:
            if now - self._pending_clap_at > self.maximum_gap_seconds:
                self._pending_clap_at = None
        return False

    def _register_clap(self, clap_at: float) -> bool:
        if clap_at - self._last_trigger_at < self.cooldown_seconds:
            return False

        previous = self._pending_clap_at
        if previous is not None:
            gap = clap_at - previous
            if self.minimum_gap_seconds <= gap <= self.maximum_gap_seconds:
                self._pending_clap_at = None
                self._last_trigger_at = clap_at
                return True
            if 0 <= gap < self.minimum_gap_seconds:
                # A very close echo belongs to the same physical clap.
                return False

        self._pending_clap_at = clap_at
        return False

    def _clap_offsets(self, audio: sr.AudioData) -> tuple[list[float], float]:
        sample_rate = max(1, int(audio.sample_rate))
        raw = audio.get_raw_data(convert_width=2)
        samples = array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if sys.byteorder != "little":
            samples.byteswap()
        duration = len(samples) / sample_rate
        if len(samples) < sample_rate // 5:
            return [], duration

        frame_size = max(80, sample_rate // 100)
        rms_values: list[float] = []
        peak_values: list[int] = []
        for start in range(0, len(samples), frame_size):
            frame = samples[start : start + frame_size]
            if len(frame) < frame_size // 2:
                break
            squares = sum(int(value) * int(value) for value in frame)
            rms_values.append(math.sqrt(squares / len(frame)))
            peak_values.append(max(abs(int(value)) for value in frame))

        if not rms_values:
            return [], duration

        noise_floor = float(statistics.median(rms_values))
        rms_threshold = max(550.0, noise_floor * 4.0)
        peak_threshold = max(2200.0, noise_floor * 7.0)
        active = [
            index
            for index, (rms, peak) in enumerate(zip(rms_values, peak_values))
            if rms >= rms_threshold and peak >= peak_threshold
        ]
        if not active:
            return [], duration

        groups: list[list[int]] = []
        for index in active:
            if groups and index - groups[-1][-1] <= 3:
                groups[-1].append(index)
            else:
                groups.append([index])

        offsets: list[float] = []
        for group in groups:
            first, last = group[0], group[-1]
            active_duration = ((last - first) + 1) * frame_size / sample_rate
            if active_duration > 0.14:
                continue

            start = max(0, (first - 1) * frame_size)
            stop = min(len(samples), (last + 2) * frame_size)
            event = samples[start:stop]
            if len(event) < 2:
                continue
            signal_energy = sum(int(value) * int(value) for value in event)
            signal_rms = math.sqrt(signal_energy / len(event))
            if signal_rms <= 0:
                continue
            difference_energy = sum(
                (int(event[index]) - int(event[index - 1])) ** 2
                for index in range(1, len(event))
            )
            difference_rms = math.sqrt(difference_energy / (len(event) - 1))
            crest_factor = max(abs(int(value)) for value in event) / signal_rms

            # Claps are brief, broadband impulses. Speech and steady knocks tend
            # to have a lower sample-to-sample change or a flatter envelope.
            if difference_rms / signal_rms < 0.45 or crest_factor < 1.45:
                continue
            offsets.append(((first + last + 1) / 2) * frame_size / sample_rate)

        return offsets, duration
