from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import servicemanager
import uvicorn
import win32event
import win32service
import win32serviceutil
import win32ts

from backend.config import AkshSettings
from backend.remote.discovery import DiscoveryPublisher
from backend.remote.tunnel import RemoteTunnel
from backend.windows_unlock.broker import MachineConfig, UnlockBroker, create_app

WTS_SESSION_LOGON = 5
WTS_SESSION_LOGOFF = 6
WTS_SESSION_LOCK = 7
WTS_SESSION_UNLOCK = 8


class ApiHost:
    def __init__(self, app, port: int, name: str):
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
                access_log=False,
                log_config=None,
            )
        )
        self.thread = threading.Thread(
            target=self.server.run, name=name, daemon=True
        )

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


class AkshUnlockService(win32serviceutil.ServiceFramework):
    _svc_name_ = "AkshPhoneUnlock"
    _svc_display_name_ = "Aksh Phone Unlock"
    _svc_description_ = (
        "Receives signed phone approvals at the Windows sign-in screen."
    )

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, True, False, None)
        self.config = MachineConfig()
        self.broker = UnlockBroker(self.config)
        self.broker.set_locked(self._initially_locked())
        self.app = create_app(self.broker, self.config.token)
        self.control_host: ApiHost | None = None
        self.public_host: ApiHost | None = None
        self.tunnel: RemoteTunnel | None = None
        self.discovery: DiscoveryPublisher | None = None
        self.monitor: threading.Thread | None = None
        self.guard = threading.RLock()

    def GetAcceptedControls(self):
        return (
            super().GetAcceptedControls()
            | win32service.SERVICE_ACCEPT_SESSIONCHANGE
        )

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcShutdown(self):
        self.SvcStop()

    def SvcOtherEx(self, control, event_type, data):
        if control != win32service.SERVICE_CONTROL_SESSIONCHANGE:
            return
        if event_type in {
            WTS_SESSION_LOCK,
            WTS_SESSION_LOGOFF,
        }:
            self.broker.set_locked(True)
        elif event_type in {
            WTS_SESSION_UNLOCK,
            WTS_SESSION_LOGON,
        }:
            self.broker.set_locked(False)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Aksh Phone Unlock service starting")
        self.control_host = ApiHost(
            self.app, self.config.control_port, "aksh-unlock-control-api"
        )
        self.control_host.start()
        self.monitor = threading.Thread(
            target=self._reconcile_public_api,
            name="aksh-unlock-public-reconcile",
            daemon=True,
        )
        self.monitor.start()
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        self._stop_public()
        if self.control_host:
            self.control_host.close()
        servicemanager.LogInfoMsg("Aksh Phone Unlock service stopped")

    def _reconcile_public_api(self) -> None:
        while (
            win32event.WaitForSingleObject(self.stop_event, 3000)
            == win32event.WAIT_TIMEOUT
        ):
            if self.broker.locked and self.public_host is None:
                if self._port_is_free(self.config.public_port):
                    self._start_public()
            elif not self.broker.locked and self.public_host is not None:
                self._stop_public()

    def _start_public(self) -> None:
        with self.guard:
            if self.public_host is not None:
                return
            settings = AkshSettings()
            settings.remote_port = self.config.public_port
            settings.remote_tunnel_enabled = True
            settings.remote_public_url = ""
            settings.remote_discovery_url = self.config.discovery_url
            host = ApiHost(
                self.app, settings.remote_port, "aksh-unlock-public-api"
            )
            host.start()
            tunnel = RemoteTunnel(settings)
            discovery = DiscoveryPublisher(settings, self.config.token)
            tunnel.start()
            discovery.start(lambda: tunnel.public_url)
            self.public_host = host
            self.tunnel = tunnel
            self.discovery = discovery

    def _stop_public(self) -> None:
        with self.guard:
            discovery, self.discovery = self.discovery, None
            tunnel, self.tunnel = self.tunnel, None
            host, self.public_host = self.public_host, None
        if discovery:
            discovery.close()
        if tunnel:
            tunnel.close()
        if host:
            host.close()

    @staticmethod
    def _port_is_free(port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    @staticmethod
    def _initially_locked() -> bool:
        try:
            session_id = win32ts.WTSGetActiveConsoleSessionId()
            if session_id == 0xFFFFFFFF:
                return True
            username = win32ts.WTSQuerySessionInformation(
                    None,
                    session_id,
                    win32ts.WTSUserName,
            )
            return not bool(str(username).strip())
        except Exception:
            return True


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(
        AkshUnlockService,
        serviceClassString=(
            "aksh_service_bootstrap.AkshUnlockService"
        ),
    )
