from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from .credentials import GroqKeyStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "data" / "settings.json"
GROQ_API_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass
class AkshSettings:
    owner_name: str = "Owner"
    assistant_name: str = "Aksh"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = GROQ_API_BASE_URL
    wake_phrases: list[str] = field(
        default_factory=lambda: ["hey aksh", "aksh suno", "okay aksh", "ok aksh"]
    )
    wake_listener_enabled: bool = True
    continuous_listening_enabled: bool = True
    double_clap_enabled: bool = True
    mute_output_while_listening: bool = True
    voice_followup_turn_limit: int = 3
    voice_lock_enabled: bool = False
    smart_environment_enabled: bool = True
    hotkey: str = "ctrl+alt+k"
    voice_match_threshold: float = 0.72
    listen_timeout_seconds: float = 8.0
    phrase_time_limit_seconds: float = 12.0
    permission_timeout_seconds: float = 8.0
    confirmation_timeout_seconds: float = 90.0
    microphone_device_index: int | None = None
    pet_x: int | None = None
    pet_y: int | None = None
    pet_size: int = 178
    language: str = "en-IN"
    tts_rate: int = 180
    tts_voice: str = "hi-IN-MadhurNeural"
    tts_neural_rate: str = "+4%"
    tts_pitch: str = "-8Hz"
    tts_volume: str = "+8%"
    groq_stt_model: str = "whisper-large-v3"
    remote_enabled: bool = True
    remote_host: str = "127.0.0.1"
    remote_port: int = 8765
    remote_token: str = ""
    remote_max_audio_mb: int = 12
    remote_tunnel_enabled: bool = True
    remote_public_url: str = ""
    remote_discovery_url: str = ""
    remote_screen_enabled: bool = False
    remote_screen_session_minutes: int = 30
    remote_screen_max_width: int = 1280
    remote_screen_fps: int = 15
    remote_screen_jpeg_quality: int = 65
    agent_enabled: bool = True
    agent_max_steps: int = 5
    agent_stop_on_failure: bool = True
    confirm_sensitive_actions: bool = True
    whatsapp_country_code: str = "91"
    full_charge_warning_limit: int = 2
    full_charge_warning_cooldown_minutes: int = 30

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def data_dir(self) -> Path:
        path = PROJECT_ROOT / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        path = PROJECT_ROOT / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path


class SettingsStore:
    def __init__(self, settings: AkshSettings, path: Path = SETTINGS_PATH):
        self.settings = settings
        self.path = path
        self._lock = threading.Lock()

    def update(self, **values: Any) -> None:
        for key, value in values.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            serializable = {
                key: value
                for key, value in asdict(self.settings).items()
                if key not in {"groq_api_key", "groq_base_url", "remote_token"}
            }
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(serializable, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary.replace(self.path)


def _read_saved_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        value = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_settings() -> tuple[AkshSettings, SettingsStore]:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = AkshSettings()
    for key, value in _read_saved_settings().items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    # The remote API is intentionally loopback-only. Cloudflared is the sole
    # public ingress, so pairing credentials never cross the LAN in plain HTTP.
    settings.remote_host = "127.0.0.1"
    settings.groq_base_url = GROQ_API_BASE_URL
    settings.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not settings.groq_api_key:
        settings.groq_api_key = GroqKeyStore(settings.data_dir).load()
    settings.groq_model = os.getenv("AKSH_GROQ_MODEL", settings.groq_model).strip()
    settings.groq_stt_model = os.getenv(
        "AKSH_GROQ_STT_MODEL", settings.groq_stt_model
    ).strip()
    environment_owner = os.getenv("AKSH_OWNER_NAME", "").strip()
    if environment_owner:
        settings.owner_name = environment_owner
    settings.remote_token = os.getenv("AKSH_REMOTE_TOKEN", "").strip()
    settings.remote_public_url = _secure_url_or_blank(
        os.getenv("AKSH_REMOTE_PUBLIC_URL", settings.remote_public_url)
    )
    settings.whatsapp_country_code = re.sub(
        r"\D",
        "",
        os.getenv(
            "AKSH_WHATSAPP_COUNTRY_CODE",
            settings.whatsapp_country_code,
        ),
    ) or "91"
    environment_discovery = os.getenv("AKSH_DISCOVERY_URL", "").strip()
    if environment_discovery:
        settings.remote_discovery_url = environment_discovery
    settings.remote_discovery_url = _secure_url_or_blank(
        settings.remote_discovery_url
    )
    store = SettingsStore(settings)
    return settings, store


def _secure_url_or_blank(value: object) -> str:
    candidate = str(value or "").strip().rstrip("/")
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return ""
    return candidate
