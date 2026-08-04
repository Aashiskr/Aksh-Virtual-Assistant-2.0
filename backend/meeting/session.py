from __future__ import annotations

import json
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import MeetingExchange, MeetingTurn, ReplyReview


class MeetingSession:
    """Thread-safe text memory for one explicitly started meeting."""

    def __init__(self, reports_dir: Path):
        self.reports_dir = reports_dir
        self._lock = threading.RLock()
        self.started_at = datetime.now().astimezone()
        self.ended_at: datetime | None = None
        self.turns: list[MeetingTurn] = []
        self.exchanges: list[MeetingExchange] = []

    def add_turn(self, source: str, text: str) -> MeetingTurn:
        turn = MeetingTurn(_clock_text(), source, " ".join(text.split()))
        with self._lock:
            self.turns.append(turn)
        return turn

    def add_exchange(
        self, question: str, answer: str, key_points: list[str]
    ) -> MeetingExchange:
        exchange = MeetingExchange(
            timestamp=_clock_text(),
            question=question,
            suggested_answer=answer,
            key_points=key_points,
        )
        with self._lock:
            self.exchanges.append(exchange)
        return exchange

    def pending_exchange(self) -> MeetingExchange | None:
        with self._lock:
            return next(
                (
                    item
                    for item in reversed(self.exchanges)
                    if not item.owner_reply
                ),
                None,
            )

    def record_reply(
        self,
        exchange: MeetingExchange,
        reply: str,
        review: ReplyReview,
    ) -> None:
        with self._lock:
            exchange.owner_reply = reply
            exchange.correction = review.correction
            exchange.better_answer = review.better_answer

    def context(self, limit: int = 28) -> str:
        with self._lock:
            turns = list(self.turns[-limit:])
        labels = {"participant": "Participant", "owner": "You"}
        return "\n".join(
            f"{labels.get(turn.source, turn.source.title())}: {turn.text}"
            for turn in turns
        )

    def transcript_text(self) -> str:
        with self._lock:
            turns = list(self.turns)
        labels = {"participant": "Participant", "owner": "You"}
        return "\n".join(
            f"[{turn.timestamp}] {labels.get(turn.source, turn.source)}: "
            f"{turn.text}"
            for turn in turns
        )

    def finish(self, summary: dict[str, Any]) -> tuple[Path, Path, str]:
        self.ended_at = datetime.now().astimezone()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        stem = self.started_at.strftime("%Y-%m-%d_%H-%M-%S")
        json_path = self.reports_dir / f"{stem}.json"
        markdown_path = self.reports_dir / f"{stem}.md"
        payload = self._payload(summary)
        temporary = json_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(json_path)
        markdown = self._markdown(summary)
        temporary_markdown = markdown_path.with_suffix(".tmp")
        temporary_markdown.write_text(markdown, encoding="utf-8")
        temporary_markdown.replace(markdown_path)
        return markdown_path, json_path, markdown

    def _payload(self, summary: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            turns = [asdict(item) for item in self.turns]
            exchanges = [asdict(item) for item in self.exchanges]
        return {
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else "",
            "summary": summary,
            "turns": turns,
            "exchanges": exchanges,
        }

    def _markdown(self, summary: dict[str, Any]) -> str:
        lines = [
            "# Aksh Meeting Report",
            "",
            f"- Started: {self.started_at.isoformat(timespec='minutes')}",
            f"- Ended: {self.ended_at.isoformat(timespec='minutes') if self.ended_at else ''}",
            "",
            "## Detailed Summary",
            "",
            str(summary.get("summary", "No summary available.")),
        ]
        for title, key in (
            ("Key Points", "key_points"),
            ("Decisions", "decisions"),
            ("Action Items", "action_items"),
            ("Follow-ups", "follow_ups"),
        ):
            lines.extend(["", f"## {title}", ""])
            values = summary.get(key, [])
            lines.extend(f"- {value}" for value in values)
            if not values:
                lines.append("- None recorded")
        lines.extend(["", "## Questions, Suggestions and Your Replies", ""])
        with self._lock:
            exchanges = list(self.exchanges)
        for index, item in enumerate(exchanges, 1):
            lines.extend(
                [
                    f"### {index}. {item.question}",
                    "",
                    f"**Aksh suggestion:** {item.suggested_answer}",
                    "",
                    f"**Your reply:** {item.owner_reply or 'No reply captured'}",
                ]
            )
            if item.correction:
                lines.extend(
                    [
                        "",
                        f"**Correction:** {item.correction}",
                        "",
                        f"**Better answer:** {item.better_answer}",
                    ]
                )
            lines.append("")
        lines.extend(["## Full Transcript", "", "```text"])
        lines.extend(self.transcript_text().splitlines())
        lines.extend(["```", ""])
        return "\n".join(lines)


def _clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")
