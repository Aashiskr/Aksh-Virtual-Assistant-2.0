from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path

from ..config import AkshSettings


LOGGER = logging.getLogger(__name__)
PUBLIC_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


class RemoteTunnel:
    """Owns the optional Cloudflare quick tunnel used outside the local Wi-Fi."""

    def __init__(self, settings: AkshSettings):
        self.settings = settings
        self.public_url = settings.remote_public_url.strip()
        self._fixed_public_url = bool(self.public_url)
        self.status = "configured" if self.public_url else "stopped"
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._watcher: threading.Thread | None = None
        self._restart_timer: threading.Timer | None = None
        self._lock = threading.RLock()
        self._closing = threading.Event()
        self._ready = threading.Event()
        if self.public_url:
            self._ready.set()

    def start(self) -> None:
        with self._lock:
            if (
                self._closing.is_set()
                or self._fixed_public_url
                or not self.settings.remote_tunnel_enabled
                or self._process
            ):
                return
            executable = self._find_executable()
            if not executable:
                self.status = "cloudflared_missing"
                LOGGER.warning(
                    "Phone remote tunnel unavailable: cloudflared missing"
                )
                return

            local_url = f"http://127.0.0.1:{self.settings.remote_port}"
            flags = subprocess.CREATE_NO_WINDOW if hasattr(
                subprocess, "CREATE_NO_WINDOW"
            ) else 0
            try:
                process = subprocess.Popen(
                    [str(executable), "tunnel", "--url", local_url],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=flags,
                )
            except OSError as exc:
                self.status = "start_failed"
                LOGGER.warning("Phone remote tunnel did not start: %s", exc)
                return
            self._process = process
            self._restart_timer = None
            self.status = "starting"
            self._reader = threading.Thread(
                target=self._read_output,
                args=(process,),
                name="aksh-remote-tunnel-output",
                daemon=True,
            )
            self._watcher = threading.Thread(
                target=self._watch_process,
                args=(process,),
                name="aksh-remote-tunnel-watchdog",
                daemon=True,
            )
            self._reader.start()
            self._watcher.start()

    def close(self) -> None:
        with self._lock:
            self._closing.set()
            restart_timer = self._restart_timer
            self._restart_timer = None
            process = self._process
            self._process = None
            self.status = "stopped"
        if restart_timer is not None:
            restart_timer.cancel()
        if not process or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

    def wait_ready(self, timeout: float = 12.0) -> bool:
        return self._ready.wait(timeout)

    def snapshot(self) -> dict[str, str]:
        return {
            "public_url": self.public_url,
            "tunnel_status": self.status,
        }

    def _read_output(self, process: subprocess.Popen[str]) -> None:
        if not process or not process.stdout:
            return
        candidate_url = ""
        for line in process.stdout:
            match = PUBLIC_URL.search(line)
            if match:
                candidate_url = match.group(0)
                with self._lock:
                    if self._process is process:
                        self.status = "registering"
            if candidate_url and "Registered tunnel connection" in line:
                with self._lock:
                    if self._process is not process:
                        continue
                    self.public_url = candidate_url
                    self.status = "connected"
                    self._ready.set()
                    LOGGER.info("Phone remote HTTPS tunnel connected")

    def _watch_process(self, process: subprocess.Popen[str]) -> None:
        return_code = process.wait()
        with self._lock:
            if self._process is not process:
                return
            self._process = None
            if not self._fixed_public_url:
                self.public_url = ""
                self._ready.clear()
            self.status = "disconnected"
            should_restart = not self._closing.is_set()
            restart_timer = (
                threading.Timer(2.0, self.start) if should_restart else None
            )
            self._restart_timer = restart_timer
        LOGGER.warning("Phone remote tunnel exited with code %s", return_code)
        if restart_timer is not None:
            restart_timer.daemon = True
            restart_timer.start()

    def _find_executable(self) -> Path | None:
        bundled = (
            self.settings.project_root
            / "infrastructure"
            / "windows"
            / "cloudflared"
            / "cloudflared.exe"
        )
        if bundled.exists():
            return bundled
        discovered = shutil.which("cloudflared")
        return Path(discovered) if discovered else None
