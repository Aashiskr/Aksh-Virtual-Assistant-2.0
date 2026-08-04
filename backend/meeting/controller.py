from __future__ import annotations

import difflib
import logging
import queue
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from ..config import AkshSettings
from .audio_capture import MeetingAudioCapture
from .brain import MeetingBrain
from .session import MeetingSession
from .transcriber import MeetingTranscriber


LOGGER = logging.getLogger(__name__)
MeetingCallback = Callable[[str, dict[str, Any]], None]


class MeetingController:
    """Coordinates isolated meeting transcription, coaching, and reporting."""

    def __init__(
        self,
        settings: AkshSettings,
        callback: MeetingCallback | None = None,
    ):
        self.settings = settings
        self.callback = callback or (lambda event, payload: None)
        self.brain = MeetingBrain(settings)
        self.transcriber = MeetingTranscriber(settings)
        self.audio = MeetingAudioCapture(
            self._queue_audio,
            self._audio_error,
            microphone_device_index=settings.microphone_device_index,
        )
        self.session: MeetingSession | None = None
        self._jobs: queue.Queue[tuple[str, bytes] | None] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._active = threading.Event()
        self._stopping = threading.Event()
        self._recent_participant: tuple[float, str] | None = None
        self._participant_window: deque[str] = deque(maxlen=3)
        self._answered_questions: list[str] = []
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self._active.is_set()

    def start(self) -> None:
        with self._lock:
            if self.active or self._stopping.is_set():
                return
            if not self.brain.enabled:
                raise RuntimeError("Meeting Mode ke liye Groq API key required hai.")
            self.session = MeetingSession(
                self.settings.data_dir / "meetings"
            )
            self._jobs = queue.Queue()
            self._participant_window.clear()
            self._answered_questions.clear()
            self._active.set()
            self._worker_thread = threading.Thread(
                target=self._worker,
                name="aksh-meeting-ai",
                daemon=True,
            )
            self._worker_thread.start()
            try:
                participant, owner = self.audio.start()
            except Exception:
                self._active.clear()
                self._jobs.put(None)
                raise
        self._emit(
            "started",
            participant_device=participant,
            owner_device=owner,
        )

    def stop_async(self) -> None:
        with self._lock:
            if not self.active or self._stopping.is_set():
                return
            self._stopping.set()
        threading.Thread(
            target=self._finish,
            name="aksh-meeting-finish",
            daemon=True,
        ).start()

    def close(self) -> None:
        if self.active and not self._stopping.is_set():
            self._stopping.set()
            self._finish()

    def _queue_audio(self, source: str, wav_data: bytes) -> None:
        if self.active:
            self._jobs.put((source, wav_data))

    def _audio_error(self, message: str) -> None:
        self._emit("error", message=message)

    def _worker(self) -> None:
        while True:
            item = self._jobs.get()
            if item is None:
                return
            source, wav_data = item
            try:
                self._process_turn(source, wav_data)
            except Exception as exc:
                LOGGER.exception("Meeting turn processing failed")
                self._emit("error", message=f"Meeting AI: {exc}")

    def _process_turn(self, source: str, wav_data: bytes) -> None:
        session = self.session
        if session is None:
            return
        text = self.transcriber.transcribe(wav_data, source)
        if not text or self._is_echo(source, text):
            return
        session.add_turn(source, text)
        self._emit("transcript", source=source, text=text)
        if source == "participant":
            self._recent_participant = (time.monotonic(), text)
            self._participant_window.append(text)
            recent_audio = " ".join(self._participant_window)
            suggestion = self.brain.suggest_answer(
                recent_audio, session.context()
            )
            if suggestion:
                question, answer, points = suggestion
                if self._question_already_answered(question):
                    self._participant_window.clear()
                    return
                session.add_exchange(question, answer, points)
                self._answered_questions.append(question)
                self._participant_window.clear()
                LOGGER.info("Meeting answer generated and sent to overlay")
                self._emit(
                    "answer",
                    question=question,
                    answer=answer,
                    key_points=points,
                )
            return
        pending = session.pending_exchange()
        if pending is None:
            return
        review = self.brain.review_reply(
            pending.question,
            pending.suggested_answer,
            text,
            session.context(),
        )
        session.record_reply(pending, text, review)
        self._emit(
            "reply_review",
            needs_correction=review.needs_correction,
            correction=review.correction,
            better_answer=review.better_answer,
            owner_reply=text,
        )

    def _is_echo(self, source: str, text: str) -> bool:
        if source != "owner" or self._recent_participant is None:
            return False
        captured_at, participant = self._recent_participant
        if time.monotonic() - captured_at > 10:
            return False
        left, right = _comparable(text), _comparable(participant)
        if min(len(left), len(right)) < 18:
            return False
        return difflib.SequenceMatcher(None, left, right).ratio() >= 0.90

    def _question_already_answered(self, question: str) -> bool:
        target = _comparable(question)
        return any(
            difflib.SequenceMatcher(
                None, target, _comparable(previous)
            ).ratio() >= 0.86
            for previous in self._answered_questions[-12:]
        )

    def _finish(self) -> None:
        try:
            self._emit("stopping")
            self.audio.stop()
            self._active.clear()
            self._jobs.put(None)
            worker = self._worker_thread
            if worker and worker is not threading.current_thread():
                worker.join(timeout=180)
            session = self.session
            if session is None:
                return
            try:
                summary = self.brain.summarize(session.transcript_text())
            except Exception as exc:
                LOGGER.exception("Meeting summary failed")
                summary = {
                    "summary": f"AI summary unavailable: {exc}",
                    "key_points": [],
                    "decisions": [],
                    "action_items": [],
                    "follow_ups": [],
                }
            markdown_path, json_path, markdown = session.finish(summary)
            self._emit(
                "finished",
                markdown_path=str(markdown_path),
                json_path=str(json_path),
                report=markdown,
            )
        finally:
            self._active.clear()
            self._stopping.clear()

    def _emit(self, event: str, **payload: Any) -> None:
        self.callback(event, payload)


def _comparable(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()
