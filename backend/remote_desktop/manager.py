from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)

from .capture import ScreenVideoTrack, capture_jpeg
from .input import RemoteInputController
from .presentation import PresentationController
from .sessions import ScreenSession, ScreenSessionStore


LOGGER = logging.getLogger(__name__)


class RemoteDesktopManager:
    def __init__(self, settings):
        self.settings = settings
        self._session_lock = threading.RLock()
        self.sessions = ScreenSessionStore(
            ttl_seconds=settings.remote_screen_session_minutes * 60,
            maximum_sessions=1,
            on_expire=self._expire_sessions,
        )
        self.input = RemoteInputController()
        self.presentation = PresentationController(
            lambda command, **options: self.input.submit_presentation(
                command,
                **options,
            ),
            magnifier_running=lambda: self.input.magnifier_running(),
        )
        self._presentation_expiry_timer: threading.Timer | None = None
        self._closed = False
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.remote_screen_enabled)

    def create_session(self) -> dict[str, object]:
        with self._session_lock:
            self._require_enabled()
            # One phone is authoritative. Remember replacement tokens so an old
            # viewer cannot auto-renew and steal control back from the new one.
            self._clear_sessions(remember_revoked=True)
            self._reset_presentation_locked()
            session = self.sessions.create()
            return {
                "session_id": session.token,
                "expires_in": round(self.sessions.ttl_seconds),
                "webrtc": True,
            }

    def require_session(self, token: str) -> ScreenSession:
        with self._session_lock:
            self._require_enabled()
            try:
                return self.sessions.require(token)
            except KeyError:
                self._reset_presentation_locked(owner=str(token))
                raise

    def remove_session(self, token: str) -> None:
        with self._session_lock:
            session = self.sessions.remove(token)
            if session is not None:
                self._close_peer(session.peer)
            self.input.revoke()
            if session is not None:
                self._reset_presentation_locked(owner=session.token)

    def capture_frame(self, token: str) -> bytes:
        self.require_session(token)
        return capture_jpeg(
            maximum_width=self.settings.remote_screen_max_width,
            quality=self.settings.remote_screen_jpeg_quality,
        )

    def submit_input(self, token: str, event: dict[str, Any]) -> None:
        with self._session_lock:
            self.require_session(token)
            self.input.submit(event)

    def presentation_state(self, token: str) -> dict[str, object]:
        with self._session_lock:
            self.require_session(token)
            return self.presentation.snapshot()

    def presentation_snapshot(self) -> dict[str, object]:
        return self.presentation.snapshot()

    def submit_presentation_action(
        self,
        token: str,
        action: object,
        *,
        x: object | None = None,
        y: object | None = None,
    ) -> dict[str, object]:
        with self._session_lock:
            self.require_session(token)
            state = self.presentation.submit(
                str(token),
                action,
                x=x,
                y=y,
            )
            if state["enabled"]:
                self._schedule_presentation_expiry_locked()
            else:
                self._cancel_presentation_expiry_locked()
            return state

    async def accept_offer(
        self,
        token: str,
        *,
        sdp: str,
        description_type: str,
    ) -> dict[str, str]:
        self.require_session(token)
        if description_type != "offer":
            raise ValueError("WebRTC offer required.")
        self._loop = asyncio.get_running_loop()

        configuration = RTCConfiguration(
            iceServers=[RTCIceServer(urls="stun:stun.cloudflare.com:3478")]
        )
        peer = RTCPeerConnection(configuration=configuration)
        try:
            previous_peer = self.sessions.attach_peer(token, peer)
            if previous_peer is not None:
                await previous_peer.close()
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
                    # Direct peers commonly fail across carrier-grade NAT.
                    # Keep the session valid for HTTPS frame/input fallback.
                    self.sessions.detach_peer(token, peer)
                    if peer.connectionState != "closed":
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
        except Exception:
            self.sessions.detach_peer(token, peer)
            await peer.close()
            raise

    def disable_all(self) -> None:
        with self._session_lock:
            self._clear_sessions()
            self._reset_presentation_locked()

    def _clear_sessions(self, *, remember_revoked: bool = False) -> None:
        sessions = self.sessions.clear(remember_revoked=remember_revoked)
        for session in sessions:
            self._close_peer(session.peer)
        self.input.revoke()

    def _expire_sessions(self, sessions: list[ScreenSession]) -> None:
        with self._session_lock:
            self.input.revoke()
            for session in sessions:
                self._close_peer(session.peer)
                self._reset_presentation_locked(owner=session.token)

    def _reset_presentation_locked(self, *, owner: str | None = None) -> bool:
        reset = self.presentation.reset(owner=owner)
        if not self.presentation.snapshot()["enabled"]:
            self._cancel_presentation_expiry_locked()
        return reset

    def _schedule_presentation_expiry_locked(self) -> None:
        if self._closed or self._presentation_expiry_timer is not None:
            return
        interval = min(30.0, max(1.0, self.sessions.ttl_seconds / 4))
        timer = threading.Timer(interval, self._check_presentation_expiry)
        timer.daemon = True
        self._presentation_expiry_timer = timer
        timer.start()

    def _cancel_presentation_expiry_locked(self) -> None:
        timer = self._presentation_expiry_timer
        self._presentation_expiry_timer = None
        if timer is not None:
            timer.cancel()

    def _check_presentation_expiry(self) -> None:
        with self._session_lock:
            self._presentation_expiry_timer = None
            self.sessions.active_count()
            if self.presentation.snapshot()["enabled"]:
                self._schedule_presentation_expiry_locked()

    def close(self) -> None:
        with self._session_lock:
            self._closed = True
            self._cancel_presentation_expiry_locked()
            self._clear_sessions()
            self.presentation.reset()
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
