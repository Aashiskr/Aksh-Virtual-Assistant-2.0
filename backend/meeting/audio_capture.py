from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from .audio_utils import AudioDevice, device_from_info, pcm_level, wav_bytes

LOGGER = logging.getLogger(__name__)
AudioCallback = Callable[[str, bytes], None]
ErrorCallback = Callable[[str], None]

@dataclass(slots=True)
class _CaptureChannel:
    source: str
    device: AudioDevice
    segmenter: "AudioSegmenter"
    trailing_silence: float
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_callback: float = field(default_factory=time.monotonic)


class AudioSegmenter:
    """Turns a continuous PCM stream into silence-delimited speech turns."""

    def __init__(
        self,
        rate: int,
        chunk_frames: int,
        *,
        minimum_level: float,
        trailing_silence: float,
        maximum_seconds: float = 28.0,
    ):
        self.rate = rate
        self.chunk_frames = chunk_frames
        self.minimum_level = minimum_level
        self.trailing_chunks = max(
            2, round(trailing_silence * rate / chunk_frames)
        )
        self.maximum_chunks = max(
            self.trailing_chunks + 1,
            round(maximum_seconds * rate / chunk_frames),
        )
        self.pre_roll: deque[bytes] = deque(
            maxlen=max(2, round(0.35 * rate / chunk_frames))
        )
        self.noise_floor = minimum_level / 3
        self.active: list[bytes] = []
        self.silent_chunks = 0
        self.voiced_chunks = 0

    def feed(self, pcm: bytes) -> bytes | None:
        level = pcm_level(pcm)
        threshold = max(self.minimum_level, self.noise_floor * 3.2)
        if not self.active:
            self.pre_roll.append(pcm)
            if level < threshold:
                self.noise_floor = (self.noise_floor * 0.96) + (level * 0.04)
                return None
            self.active = list(self.pre_roll)
            self.pre_roll.clear()
            self.silent_chunks = 0
            self.voiced_chunks = 1
            return None

        self.active.append(pcm)
        if level < max(self.minimum_level, self.noise_floor * 2.0):
            self.silent_chunks += 1
        else:
            self.silent_chunks = 0
            self.voiced_chunks += 1
        if (
            self.silent_chunks >= self.trailing_chunks
            or len(self.active) >= self.maximum_chunks
        ):
            return self._complete()
        return None

    def flush(self) -> bytes | None:
        return self._complete() if self.active else None

    def _complete(self) -> bytes | None:
        raw = b"".join(self.active)
        self.active = []
        self.silent_chunks = 0
        voiced_chunks = self.voiced_chunks
        self.voiced_chunks = 0
        minimum_chunks = max(2, round(0.45 * self.rate / self.chunk_frames))
        return raw if voiced_chunks >= minimum_chunks else None


class MeetingAudioCapture:
    def __init__(
        self,
        on_audio: AudioCallback,
        on_error: ErrorCallback,
        microphone_device_index: int | None = None,
    ):
        self.on_audio = on_audio
        self.on_error = on_error
        self.microphone_device_index = microphone_device_index
        self._stop = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._audio = None
        self._streams: list = []
        self._channels: list[_CaptureChannel] = []
        self._participant_active_until = 0.0
        self.participant_device: AudioDevice | None = None
        self.owner_device: AudioDevice | None = None

    def start(self) -> tuple[str, str]:
        if self._audio is not None:
            raise RuntimeError("Meeting audio capture already running.")
        self._stop.clear()
        self._participant_active_until = 0.0
        try:
            import pyaudiowpatch as pyaudio
        except ImportError as exc:
            raise RuntimeError(
                "Meeting audio dependency missing hai. setup.py dobara run karein."
            ) from exc
        self._audio = pyaudio.PyAudio()
        try:
            self.participant_device, self.owner_device = self._resolve_devices(
                self._audio,
                self.microphone_device_index,
            )
            for source, device, silence, level in (
                ("participant", self.participant_device, 1.0, 0.0025),
                ("owner", self.owner_device, 1.8, 0.009),
            ):
                channel = self._channel(source, device, silence, level)
                stream = self._open_stream(channel, pyaudio)
                self._channels.append(channel)
                self._streams.append(stream)
        except Exception:
            self._close_audio()
            raise
        self._monitor_thread = threading.Thread(
            target=self._monitor,
            name="aksh-meeting-audio-monitor",
            daemon=True,
        )
        self._monitor_thread.start()
        return self.participant_device.name, self.owner_device.name

    def stop(self) -> None:
        self._stop.set()
        for stream in self._streams:
            try:
                if stream.is_active():
                    stream.stop_stream()
            except Exception:
                pass
        if self._monitor_thread:
            self._monitor_thread.join(timeout=3)
        for channel in self._channels:
            self._flush_channel(channel)
        self._close_audio()
        self._monitor_thread = None

    @staticmethod
    def _resolve_devices(
        audio, microphone_device_index: int | None
    ) -> tuple[AudioDevice, AudioDevice]:
        loopback = audio.get_default_wasapi_loopback()
        microphone = (
            audio.get_device_info_by_index(microphone_device_index)
            if microphone_device_index is not None
            else audio.get_default_input_device_info()
        )
        if int(microphone.get("maxInputChannels", 0)) < 1:
            raise RuntimeError("Selected meeting microphone input device nahi hai.")
        return device_from_info(loopback), device_from_info(microphone)

    @staticmethod
    def _channel(
        source: str,
        device: AudioDevice,
        trailing_silence: float,
        minimum_level: float,
    ) -> _CaptureChannel:
        chunk_frames = max(480, round(device.rate * 0.05))
        return _CaptureChannel(
            source=source,
            device=device,
            trailing_silence=trailing_silence,
            segmenter=AudioSegmenter(
                device.rate,
                chunk_frames,
                minimum_level=minimum_level,
                trailing_silence=trailing_silence,
                maximum_seconds=(
                    8.0 if source == "participant" else 24.0
                ),
            ),
        )

    def _open_stream(
        self,
        channel: _CaptureChannel,
        pyaudio,
    ):
        def receive(pcm, frame_count, time_info, status):
            del frame_count, time_info
            if status:
                LOGGER.debug(
                    "Meeting %s audio status: %s", channel.source, status
                )
            now = time.monotonic()
            channel.last_callback = now
            if (
                channel.source == "participant"
                and pcm_level(pcm) >= channel.segmenter.minimum_level
            ):
                self._participant_active_until = now + 0.4
            elif (
                channel.source == "owner"
                and now < self._participant_active_until
            ):
                pcm = bytes(len(pcm))
            with channel.lock:
                complete = channel.segmenter.feed(pcm)
            if complete:
                self._emit_audio(channel, complete)
            flag = (
                pyaudio.paComplete
                if self._stop.is_set()
                else pyaudio.paContinue
            )
            return None, flag

        return self._audio.open(
            format=pyaudio.paInt16,
            channels=channel.device.channels,
            rate=channel.device.rate,
            input=True,
            input_device_index=channel.device.index,
            frames_per_buffer=channel.segmenter.chunk_frames,
            stream_callback=receive,
        )

    def _monitor(self) -> None:
        while not self._stop.wait(0.1):
            now = time.monotonic()
            for channel in self._channels:
                if (
                    now - channel.last_callback
                    > channel.trailing_silence + 0.25
                ):
                    self._flush_channel(channel)

    def _flush_channel(self, channel: _CaptureChannel) -> None:
        with channel.lock:
            complete = channel.segmenter.flush()
        if complete:
            self._emit_audio(channel, complete)

    def _emit_audio(self, channel: _CaptureChannel, pcm: bytes) -> None:
        self.on_audio(
            channel.source,
            wav_bytes(pcm, channel.device),
        )

    def _close_audio(self) -> None:
        for stream in self._streams:
            try:
                stream.close()
            except Exception:
                pass
        self._streams.clear()
        self._channels.clear()
        if self._audio is not None:
            try:
                self._audio.terminate()
            except Exception:
                pass
            self._audio = None
