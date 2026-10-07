from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field


class WebRtcOffer(BaseModel):
    sdp: str = Field(min_length=20, max_length=200_000)
    type: Literal["offer"]


class RemoteInput(BaseModel):
    action: str = Field(min_length=1, max_length=32)
    x: float | None = None
    y: float | None = None
    delta: int | None = None
    text: str | None = Field(default=None, max_length=1000)
    key: str | None = Field(default=None, max_length=32)


class PresentationAction(BaseModel):
    action: Literal[
        "enable",
        "disable",
        "toggle",
        "next",
        "previous",
        "zoom_in",
        "zoom_out",
        "zoom_reset",
    ]
    x: float | None = Field(default=None, ge=0.0, le=1.0)
    y: float | None = Field(default=None, ge=0.0, le=1.0)


def _session_http_error(exception: Exception) -> HTTPException:
    if isinstance(exception, PermissionError):
        return HTTPException(status_code=403, detail=str(exception))
    return HTTPException(status_code=401, detail=str(exception))


def attach_remote_desktop_routes(
    app: FastAPI,
    manager,
    authorize: Callable,
) -> None:
    def session_header(
        value: str = Header(default="", alias="X-Aksh-Screen-Session"),
    ) -> str:
        if not value:
            raise HTTPException(status_code=401, detail="Screen session required")
        try:
            manager.require_session(value)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return value

    @app.get("/v1/screen/status")
    def screen_status(_: None = Depends(authorize)) -> dict[str, object]:
        return {
            "enabled": manager.enabled,
            "active_sessions": manager.sessions.active_count(),
        }

    @app.post("/v1/screen/sessions", status_code=201)
    def create_session(_: None = Depends(authorize)) -> dict[str, object]:
        try:
            return manager.create_session()
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.delete("/v1/screen/sessions/current", status_code=204)
    def remove_session(
        _: None = Depends(authorize),
        session: str = Depends(session_header),
    ) -> Response:
        manager.remove_session(session)
        return Response(status_code=204)

    @app.post("/v1/screen/sessions/current/heartbeat")
    def keep_session_alive(
        _: None = Depends(authorize),
        session: str = Depends(session_header),
    ) -> dict[str, bool]:
        return {"active": True}

    @app.get("/v1/screen/frame")
    def screen_frame(
        _: None = Depends(authorize),
        session: str = Depends(session_header),
    ) -> Response:
        try:
            content = manager.capture_frame(session)
        except (KeyError, PermissionError) as exc:
            raise _session_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return Response(
            content=content,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @app.post("/v1/screen/input", status_code=202)
    def screen_input(
        event: RemoteInput,
        _: None = Depends(authorize),
        session: str = Depends(session_header),
    ) -> dict[str, bool]:
        try:
            manager.submit_input(session, event.model_dump(exclude_none=True))
        except (KeyError, PermissionError) as exc:
            raise _session_http_error(exc) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"accepted": True}

    @app.get("/v1/screen/presentation")
    def presentation_state(
        response: Response,
        _: None = Depends(authorize),
        session: str = Depends(session_header),
    ) -> dict[str, object]:
        response.headers["Cache-Control"] = "no-store"
        try:
            return manager.presentation_state(session)
        except (KeyError, PermissionError) as exc:
            raise _session_http_error(exc) from exc

    @app.post("/v1/screen/presentation/actions")
    def presentation_action(
        request: PresentationAction,
        _: None = Depends(authorize),
        session: str = Depends(session_header),
    ) -> dict[str, object]:
        try:
            options = request.model_dump(exclude_none=True)
            action = options.pop("action")
            return manager.submit_presentation_action(
                session,
                action,
                **options,
            )
        except (KeyError, PermissionError) as exc:
            raise _session_http_error(exc) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/screen/webrtc/offer")
    async def webrtc_offer(
        offer: WebRtcOffer,
        _: None = Depends(authorize),
        session: str = Depends(session_header),
    ) -> dict[str, Any]:
        try:
            return await manager.accept_offer(
                session,
                sdp=offer.sdp,
                description_type=offer.type,
            )
        except (KeyError, PermissionError) as exc:
            raise _session_http_error(exc) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
