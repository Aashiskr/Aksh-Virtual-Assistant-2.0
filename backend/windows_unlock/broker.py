from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
import struct
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pywintypes
import win32crypt
import win32event
import win32file
import win32pipe
import win32security
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.hashes import SHA256
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


PROGRAM_DATA = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Aksh"
CONFIG_PATH = PROGRAM_DATA / "phone_unlock.json"
PHONE_KEY_PATH = PROGRAM_DATA / "phone_unlock_key.json"
READY_EVENT = r"Global\AkshPhoneUnlockReady"
CREDENTIAL_PIPE = r"\\.\pipe\AkshPhoneUnlockCredential"
PIPE_MAGIC = 0x48534B41
CHALLENGE_PREFIX = b"AKSH-WINDOWS-UNLOCK-V1\0"
CHALLENGE_SECONDS = 60
MAX_PUBLIC_KEY_BYTES = 2048
MAX_SIGNATURE_BYTES = 512


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    encoded = value.encode("ascii")
    return base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))


class MachineConfig:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.value = json.loads(path.read_text(encoding="utf-8-sig"))

    @property
    def token(self) -> str:
        return self._unprotect("token_blob").decode("utf-8")

    @property
    def discovery_url(self) -> str:
        return str(self.value.get("discovery_url", "")).strip()

    @property
    def public_port(self) -> int:
        return int(self.value.get("public_port", 8765))

    @property
    def control_port(self) -> int:
        return int(self.value.get("control_port", 8766))

    def credential(self) -> tuple[str, str, str]:
        value = json.loads(self._unprotect("credential_blob").decode("utf-8"))
        domain = str(value.get("domain", "")).strip()
        username = str(value.get("username", "")).strip()
        password = str(value.get("password", ""))
        if not domain or not username or not password:
            raise ValueError("The encrypted Windows credential is incomplete")
        return domain, username, password

    def _unprotect(self, key: str) -> bytes:
        protected = base64.b64decode(str(self.value[key]))
        return win32crypt.CryptUnprotectData(
            protected, None, None, None, 0
        )[1]


class EnrollRequest(BaseModel):
    public_key: str = Field(min_length=20, max_length=4096)
    device_label: str = Field(default="Android phone", max_length=120)


class ApproveRequest(BaseModel):
    challenge_id: str = Field(min_length=20, max_length=80)
    signature: str = Field(min_length=20, max_length=2048)


class UnlockBroker:
    def __init__(self, config: MachineConfig):
        self.config = config
        self.boot_id = str(uuid.uuid4())
        self._locked = True
        self._lock = threading.RLock()
        self._challenges: dict[str, tuple[bytes, float]] = {}
        self._ready_event = win32event.CreateEvent(
            self._system_security_attributes(), False, False, READY_EVENT
        )

    @property
    def locked(self) -> bool:
        with self._lock:
            return self._locked

    def set_locked(self, value: bool) -> None:
        with self._lock:
            self._locked = bool(value)
            if not self._locked:
                self._challenges.clear()

    def health(self) -> dict[str, Any]:
        enrolled = self._phone_key() is not None
        return {
            "ok": True,
            "assistant": "Aksh",
            "computer_state": "locked" if self.locked else "unlocked",
            "unlock_available": enrolled,
            "phone_enrolled": enrolled,
            "boot_id": self.boot_id,
        }

    def enroll(self, request: EnrollRequest) -> dict[str, Any]:
        try:
            der = _b64decode(request.public_key)
            if len(der) > MAX_PUBLIC_KEY_BYTES:
                raise ValueError("Public key is too large")
            public_key = serialization.load_der_public_key(der)
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, "Invalid phone public key") from exc
        if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(
            public_key.curve, ec.SECP256R1
        ):
            raise HTTPException(400, "Aksh requires a P-256 phone key")

        existing = self._phone_key_bytes()
        if existing is not None and not hmac.compare_digest(existing, der):
            raise HTTPException(
                409,
                "A different phone is already enrolled. Reset it locally on the laptop.",
            )
        if existing is None:
            value = {
                "public_key": _b64encode(der),
                "device_label": request.device_label.strip() or "Android phone",
                "enrolled_at": int(time.time()),
            }
            temporary = PHONE_KEY_PATH.with_suffix(".tmp")
            temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
            temporary.replace(PHONE_KEY_PATH)
        return {"enrolled": True}

    def create_challenge(self) -> dict[str, Any]:
        if not self.locked:
            raise HTTPException(409, "The laptop is already unlocked")
        if self._phone_key() is None:
            raise HTTPException(409, "No phone is enrolled")
        challenge_id = str(uuid.uuid4())
        nonce = secrets.token_bytes(32)
        payload = CHALLENGE_PREFIX + challenge_id.encode("ascii") + b"\0" + nonce
        now = time.monotonic()
        with self._lock:
            self._challenges = {
                key: value
                for key, value in self._challenges.items()
                if value[1] > now
            }
            self._challenges[challenge_id] = (payload, now + CHALLENGE_SECONDS)
        return {
            "challenge_id": challenge_id,
            "payload": _b64encode(payload),
            "expires_in": CHALLENGE_SECONDS,
        }

    def approve(self, request: ApproveRequest) -> dict[str, Any]:
        if not self.locked:
            raise HTTPException(409, "The laptop is already unlocked")
        with self._lock:
            challenge = self._challenges.pop(request.challenge_id, None)
        if challenge is None or challenge[1] <= time.monotonic():
            raise HTTPException(410, "Unlock request expired. Please try again.")
        try:
            signature = _b64decode(request.signature)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(400, "Invalid signature encoding") from exc
        if len(signature) > MAX_SIGNATURE_BYTES:
            raise HTTPException(400, "Signature is too large")
        public_key = self._phone_key()
        if public_key is None:
            raise HTTPException(409, "No phone is enrolled")
        try:
            public_key.verify(signature, challenge[0], ec.ECDSA(SHA256()))
        except InvalidSignature as exc:
            raise HTTPException(
                401, "Fingerprint approval signature was rejected"
            ) from exc

        domain, username, password = self.config.credential()
        worker = threading.Thread(
            target=self._serve_credential_once,
            args=(domain, username, password),
            name="aksh-unlock-credential-pipe",
            daemon=True,
        )
        worker.start()
        win32event.SetEvent(self._ready_event)
        return {"approved": True, "state": "unlocking"}

    def _phone_key_bytes(self) -> bytes | None:
        try:
            value = json.loads(PHONE_KEY_PATH.read_text(encoding="utf-8"))
            return _b64decode(str(value["public_key"]))
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return None

    def _phone_key(self) -> ec.EllipticCurvePublicKey | None:
        value = self._phone_key_bytes()
        if value is None:
            return None
        try:
            key = serialization.load_der_public_key(value)
        except ValueError:
            return None
        return key if isinstance(key, ec.EllipticCurvePublicKey) else None

    def _serve_credential_once(
        self, domain: str, username: str, password: str
    ) -> None:
        pipe = None
        try:
            pipe = win32pipe.CreateNamedPipe(
                CREDENTIAL_PIPE,
                win32pipe.PIPE_ACCESS_OUTBOUND,
                win32pipe.PIPE_TYPE_BYTE
                | win32pipe.PIPE_READMODE_BYTE
                | win32pipe.PIPE_WAIT,
                1,
                16384,
                16384,
                30000,
                self._system_security_attributes(),
            )
            try:
                win32pipe.ConnectNamedPipe(pipe, None)
            except pywintypes.error as exception:
                if exception.winerror != 535:
                    raise
            fields = [
                bytearray(domain.encode("utf-16-le")),
                bytearray(username.encode("utf-16-le")),
                bytearray(password.encode("utf-16-le")),
            ]
            header = struct.pack(
                "<4I", PIPE_MAGIC, len(fields[0]), len(fields[1]), len(fields[2])
            )
            win32file.WriteFile(pipe, header + b"".join(fields))
            win32file.FlushFileBuffers(pipe)
            for field in fields:
                field[:] = b"\0" * len(field)
        except pywintypes.error:
            return
        finally:
            password = ""
            if pipe is not None:
                try:
                    win32pipe.DisconnectNamedPipe(pipe)
                except pywintypes.error:
                    pass
                win32file.CloseHandle(pipe)

    @staticmethod
    def _system_security_attributes() -> pywintypes.SECURITY_ATTRIBUTES:
        descriptor = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            "D:P(A;;GA;;;SY)(A;;GA;;;BA)",
            win32security.SDDL_REVISION_1,
        )
        attributes = pywintypes.SECURITY_ATTRIBUTES()
        attributes.SECURITY_DESCRIPTOR = descriptor
        return attributes


def create_app(broker: UnlockBroker, token: str) -> FastAPI:
    app = FastAPI(
        title="Aksh Windows Unlock Broker",
        version="1.0.0",
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
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(401, "Invalid pairing token")

    @app.get("/v1/health")
    def health(_: None = Depends(authorize)) -> dict[str, Any]:
        return broker.health()

    @app.post("/v1/unlock/enroll")
    def enroll(
        request: EnrollRequest, _: None = Depends(authorize)
    ) -> dict[str, Any]:
        return broker.enroll(request)

    @app.post("/v1/unlock/challenge")
    def challenge(_: None = Depends(authorize)) -> dict[str, Any]:
        return broker.create_challenge()

    @app.post("/v1/unlock/approve")
    def approve(
        request: ApproveRequest, _: None = Depends(authorize)
    ) -> dict[str, Any]:
        return broker.approve(request)

    return app
