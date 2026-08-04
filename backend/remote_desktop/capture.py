from __future__ import annotations

import asyncio
from fractions import Fraction
from io import BytesIO

import mss
import numpy as np
from av import VideoFrame
from PIL import Image
from aiortc import VideoStreamTrack


VIDEO_CLOCK = 90_000


def capture_jpeg(*, maximum_width: int = 1280, quality: int = 65) -> bytes:
    with mss.mss() as capture:
        monitor = capture.monitors[1]
        shot = capture.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.rgb)
    if image.width > maximum_width:
        height = max(1, round(image.height * maximum_width / image.width))
        image = image.resize((maximum_width, height), Image.Resampling.LANCZOS)
    stream = BytesIO()
    image.save(
        stream,
        format="JPEG",
        quality=max(35, min(85, int(quality))),
        optimize=True,
    )
    return stream.getvalue()


class ScreenVideoTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, *, fps: int = 15, maximum_width: int = 1280):
        super().__init__()
        self.fps = max(5, min(30, int(fps)))
        self.maximum_width = max(640, min(1920, int(maximum_width)))
        self._capture = None
        self._pts = 0
        self._next_at: float | None = None

    async def recv(self) -> VideoFrame:
        loop = asyncio.get_running_loop()
        interval = 1 / self.fps
        now = loop.time()
        self._next_at = now if self._next_at is None else self._next_at + interval
        if self._next_at > now:
            await asyncio.sleep(self._next_at - now)
        elif now - self._next_at > interval * 2:
            self._next_at = now

        if self._capture is None:
            self._capture = mss.mss()
        monitor = self._capture.monitors[1]
        shot = self._capture.grab(monitor)
        frame = VideoFrame.from_ndarray(np.asarray(shot), format="bgra")
        if frame.width > self.maximum_width:
            height = max(
                1,
                round(frame.height * self.maximum_width / frame.width),
            )
            frame = frame.reformat(width=self.maximum_width, height=height)
        self._pts += round(VIDEO_CLOCK / self.fps)
        frame.pts = self._pts
        frame.time_base = Fraction(1, VIDEO_CLOCK)
        return frame

    def stop(self) -> None:
        capture = self._capture
        self._capture = None
        if capture is not None:
            capture.close()
        super().stop()
