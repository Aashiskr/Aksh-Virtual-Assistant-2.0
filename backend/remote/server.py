from __future__ import annotations

import hmac
import queue
import threading
from collections.abc import Callable
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..calendar_meetings import MeetingStore, public_meeting
from ..config import AkshSettings
from ..integrations.groq_speech import GroqSpeechTranscriber
from ..remote_desktop import RemoteDesktopManager, attach_remote_desktop_routes
from ..windows_unlock import WindowsUnlockClient, attach_windows_unlock_routes
from .credentials import PairingTokenStore
from .discovery import DiscoveryPublisher
from .jobs import RemoteJobStore
from .tunnel import RemoteTunnel


class TextCommand(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class RemoteCommandServer:
    def __init__(
        self,
        settings: AkshSettings,
        command_handler: Callable[[str], str],
    ):
        self.settings = settings
        self.command_handler = command_handler
        self.token = self._load_token()
        self.unlock = WindowsUnlockClient(self.token)
        self.discovery = DiscoveryPublisher(settings, self.token)
        self.jobs = RemoteJobStore()
        self.meetings = MeetingStore(settings.data_dir / "meetings.json")
        self.transcriber = GroqSpeechTranscriber(settings)
        self.screen = RemoteDesktopManager(settings)
        self.pending: queue.Queue[tuple[str, str, object] | None] = queue.Queue()
        self._closing = threading.Event()
        self._worker: threading.Thread | None = None
        self._server = None
        self._server_thread: threading.Thread | None = None
        self.tunnel = RemoteTunnel(settings)
        self.app = self._create_app()

    def start(self) -> None:
        if not self.settings.remote_enabled or self._server_thread:
            return
        import uvicorn

        self._worker = threading.Thread(
            target=self._run_jobs,
            name="aksh-remote-jobs",
            daemon=True,
        )
        self._worker.start()
        config = uvicorn.Config(
            self.app,
            host=self.settings.remote_host,
            port=self.settings.remote_port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._server_thread = threading.Thread(
            target=self._server.run,
            name="aksh-remote-api",
            daemon=True,
        )
        self._server_thread.start()
        self.tunnel.start()
        self.discovery.start(lambda: self.tunnel.public_url)

    def close(self) -> None:
        self._closing.set()
        self.pending.put(None)
        if self._server:
            self._server.should_exit = True
        self.discovery.close()
        self.tunnel.close()
        self.screen.close()

    def set_screen_enabled(self, enabled: bool) -> None:
        self.settings.remote_screen_enabled = bool(enabled)
        if not enabled:
            self.screen.disable_all()

    def connection_info(self) -> dict[str, object]:
        return {
            "enabled": self.settings.remote_enabled,
            "local_url": f"http://127.0.0.1:{self.settings.remote_port}",
            "token": self.token,
            "device_id": self.discovery.device_id,
            "discovery_enabled": self.discovery.enabled,
            "discovery_url": self.settings.remote_discovery_url,
            **self.tunnel.snapshot(),
        }

    def _create_app(self) -> FastAPI:
        app = FastAPI(
            title="Aksh Remote API",
            version="2.0.0",
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )

        def authorize(authorization: str = Header(default="")) -> None:
            supplied = (
                authorization[7:]
                if authorization.casefold().startswith("bearer ")
                else ""
            )
            if not supplied or not hmac.compare_digest(supplied, self.token):
                raise HTTPException(status_code=401, detail="Invalid pairing token")

        @app.get("/v1/health")
        def health(_: None = Depends(authorize)) -> dict[str, object]:
            return {
                "ok": True,
                "assistant": self.settings.assistant_name,
                "remote_screen": self.screen.enabled,
                **self.unlock.health(),
            }

        @app.post("/v1/commands/text", status_code=202)
        def text_command(
            command: TextCommand, _: None = Depends(authorize)
        ) -> dict[str, str]:
            job = self.jobs.create()
            self.pending.put((job.id, "text", command.text.strip()))
            return {"job_id": job.id, "state": job.state}

        @app.post("/v1/commands/audio", status_code=202)
        async def audio_command(
            audio: UploadFile = File(...), _: None = Depends(authorize)
        ) -> dict[str, str]:
            maximum = self.settings.remote_max_audio_mb * 1024 * 1024
            content = await audio.read(maximum + 1)
            if not content or len(content) > maximum:
                raise HTTPException(
                    status_code=413,
                    detail="Audio empty hai ya size limit se bada hai.",
                )
            job = self.jobs.create()
            suffix = Path(audio.filename or "command.m4a").suffix.lower()
            if suffix not in {".m4a", ".mp3", ".wav", ".ogg", ".webm"}:
                suffix = ".m4a"
            folder = self.settings.data_dir / "remote_uploads"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{job.id}{suffix}"
            path.write_bytes(content)
            self.pending.put((job.id, "audio", path))
            return {"job_id": job.id, "state": job.state}

        @app.get("/v1/commands/{job_id}")
        def command_status(
            job_id: str, _: None = Depends(authorize)
        ) -> dict[str, object]:
            job = self.jobs.get(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Command not found")
            return job.public()

        @app.get("/v1/meetings/latest")
        def latest_meeting(
            _: None = Depends(authorize),
        ) -> dict[str, object]:
            meeting = public_meeting(self.meetings.latest())
            if not meeting:
                raise HTTPException(status_code=404, detail="Meeting not found")
            return meeting

        attach_remote_desktop_routes(app, self.screen, authorize)
        attach_windows_unlock_routes(app, self.unlock, authorize)

        return app

    def _run_jobs(self) -> None:
        while not self._closing.is_set():
            item = self.pending.get()
            if item is None:
                return
            job_id, kind, payload = item
            heard = ""
            previous_meeting_id = self.meetings.latest_id()
            try:
                self.jobs.processing(job_id)
                if kind == "audio":
                    path = Path(payload)
                    heard = self.transcriber.transcribe_path(path)
                    path.unlink(missing_ok=True)
                else:
                    heard = str(payload).strip()
                self.jobs.processing(job_id, heard)
                report = self.command_handler(heard)
                latest = self.meetings.latest()
                meeting = (
                    public_meeting(latest)
                    if latest
                    and str(latest.get("id") or "") != previous_meeting_id
                    else None
                )
                self.jobs.complete(job_id, heard, report, meeting=meeting)
            except Exception as exc:
                if kind == "audio":
                    Path(payload).unlink(missing_ok=True)
                self.jobs.fail(job_id, str(exc), heard)

    def _load_token(self) -> str:
        return PairingTokenStore(self.settings.data_dir).load_or_create(
            self.settings.remote_token
        )
