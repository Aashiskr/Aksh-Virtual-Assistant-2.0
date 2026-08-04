from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)

from .capture import ScreenVideoTrack, capture_jpeg
from .input import RemoteInputController
from .sessions import ScreenSession, ScreenSessionStore


LOGGER = logging.getLogger(__name__)


class RemoteDesktopManager:
    def __init__(self, settings):
        self.settings = settings
        self.sessions = ScreenSessionStore(
            ttl_seconds=settings.remote_screen_session_minutes * 60,
        )
        self.input = RemoteInputController()
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.remote_screen_enabled)

    def create_session(self) -> dict[str, object]:
        self._require_enabled()
        # Personal-use mode keeps one authoritative phone session. Reconnecting
        # therefore revokes the previous session and its WebRTC peer immediately.
        self.disable_all()
        session = self.sessions.create()
        return {
            "session_id": session.token,
            "expires_in": round(self.sessions.ttl_seconds),
            "webrtc": True,
        }

    def require_session(self, token: str) -> ScreenSession:
        self._require_enabled()
        return self.sessions.require(token)

    def remove_session(self, token: str) -> None:
        session = self.sessions.remove(token)
        if session is not None:
            self._close_peer(session.peer)
        self.input.release()

    def capture_frame(self, token: str) -> bytes:
        self.require_session(token)
        return capture_jpeg(
            maximum_width=self.settings.remote_screen_max_width,
            quality=self.settings.remote_screen_jpeg_quality,
        )

    def submit_input(self, token: str, event: dict[str, Any]) -> None:
        self.require_session(token)
        self.input.submit(event)

    async def accept_offer(
        self,
        token: str,
        *,
        sdp: str,
        description_type: str,
    ) -> dict[str, str]:
        session = self.require_session(token)
        if description_type != "offer":
            raise ValueError("WebRTC offer required.")
        self._loop = asyncio.get_running_loop()
        if session.peer is not None:
            await session.peer.close()

        configuration = RTCConfiguration(
            iceServers=[RTCIceServer(urls="stun:stun.cloudflare.com:3478")]
        )
        peer = RTCPeerConnection(configuration=configuration)
        session.peer = peer
        peer.addTrack(
            ScreenVideoTrack(
                fps=self.settings.remote_screen_fps,
                maximum_width=self.settings.remote_screen_max_width,
            )
        )

        @peer.on("datachannel")
        def on_datachannel(channel) -> None:
            if channel.label != "input":
                return

            @channel.on("message")
            def on_message(message) -> None:
                try:
                    payload = json.loads(str(message))
                    self.submit_input(token, payload)
                except (KeyError, TypeError, ValueError, RuntimeError):
                    return

        @peer.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            if peer.connectionState in {"failed", "closed"}:
                stored = self.sessions.remove(token)
                if stored is not None and peer.connectionState != "closed":
                    await peer.close()

        await peer.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type=description_type)
        )
        answer = await peer.createAnswer()
        await peer.setLocalDescription(answer)
        return {
            "sdp": peer.localDescription.sdp,
            "type": peer.localDescription.type,
        }

    def disable_all(self) -> None:
        for session in self.sessions.clear():
            self._close_peer(session.peer)
        self.input.release()

    def close(self) -> None:
        self.disable_all()
        self.input.close()

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise PermissionError(
                "Laptop pet par Remote screen access enable karein."
            )

    def _close_peer(self, peer: object | None) -> None:
        if peer is None:
            return
        loop = self._loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(peer.close(), loop)
        else:
            LOGGER.debug("Remote screen peer will close with its event loop")
