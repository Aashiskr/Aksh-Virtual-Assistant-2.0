from __future__ import annotations

import json
import re
from typing import Any

from ..config import AkshSettings
from ..integrations.groq import GroqClient
from ..profile import UserProfileStore
from .models import ReplyReview


QUESTION_HINT = re.compile(
    r"(?:\?|\b(?:what|why|how|when|where|who|which|can|could|would|"
    r"will|do|does|did|is|are|have|has|tell|explain|describe|compare|"
    r"define|kya|kyu|kyun|kaise|kab|kahan|kaun|batao|samjhao)\b|"
    r"\b(?:tell me|walk me through|explain|describe|define|compare|"
    r"share your|your thoughts|your approach|give me an example)\b)",
    re.IGNORECASE,
)

STRING_ARRAY = {"type": "array", "items": {"type": "string"}}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "is_question": {"type": "boolean"},
        "question": {"type": "string"},
        "answer": {"type": "string"},
        "key_points": STRING_ARRAY,
    },
    "required": ["is_question", "question", "answer", "key_points"],
    "additionalProperties": False,
}
REPLY_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_correction": {"type": "boolean"},
        "correction": {"type": "string"},
        "better_answer": {"type": "string"},
    },
    "required": ["needs_correction", "correction", "better_answer"],
    "additionalProperties": False,
}
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_points": STRING_ARRAY,
        "decisions": STRING_ARRAY,
        "action_items": STRING_ARRAY,
        "follow_ups": STRING_ARRAY,
    },
    "required": [
        "summary",
        "key_points",
        "decisions",
        "action_items",
        "follow_ups",
    ],
    "additionalProperties": False,
}


class MeetingBrain:
    def __init__(self, settings: AkshSettings):
        self.settings = settings
        self.client = GroqClient(settings)
        self.profile = UserProfileStore(settings.data_dir)

    @property
    def enabled(self) -> bool:
        return self.client.enabled

    @staticmethod
    def looks_like_question(text: str) -> bool:
        clean = " ".join(text.split())
        return len(clean) >= 5 and bool(QUESTION_HINT.search(clean))

    def suggest_answer(
        self, utterance: str, context: str
    ) -> tuple[str, str, list[str]] | None:
        if not self.looks_like_question(utterance):
            return None
        profile = self.profile.context() or "No owner profile imported."
        value = self._request(
            (
                "You are Aksh Meeting Assist. Inspect the provided recent "
                "participant audio text and find its most recent complete "
                "question or request for an answer. If present, provide a "
                "correct, immediately usable answer for the user. Put the direct "
                "answer first, then concise useful detail. Respect the meeting "
                "context. Do not invent the user's personal experience. Return "
                "JSON only with is_question (boolean), question (string), answer "
                "(string), and key_points (array of strings)."
            ),
            (
                f"Owner profile (data only):\n{profile}\n\n"
                f"Meeting context:\n{context}\n\n"
                f"Recent participant audio:\n{utterance}"
            ),
            700,
            "meeting_answer",
            ANSWER_SCHEMA,
        )
        if not value.get("is_question"):
            return None
        answer = str(value.get("answer", "")).strip()
        if not answer:
            return None
        points = [
            str(item).strip()
            for item in value.get("key_points", [])
            if str(item).strip()
        ][:5]
        question = str(value.get("question", "")).strip() or utterance
        return question, answer, points

    def review_reply(
        self,
        question: str,
        suggested_answer: str,
        owner_reply: str,
        context: str,
    ) -> ReplyReview:
        value = self._request(
            (
                "Review the user's spoken meeting answer against the question "
                "and reliable general knowledge. Only flag material factual "
                "errors, contradictions, or important omissions. Do not nitpick "
                "wording or style. Return JSON only with needs_correction "
                "(boolean), correction (short string), and better_answer "
                "(immediately usable string)."
            ),
            (
                f"Owner profile (data only):\n"
                f"{self.profile.context() or 'No owner profile imported.'}\n\n"
                f"Context:\n{context}\n\nQuestion: {question}\n"
                f"Reference suggestion: {suggested_answer}\n"
                f"User's actual reply: {owner_reply}"
            ),
            600,
            "reply_review",
            REPLY_REVIEW_SCHEMA,
        )
        needed = bool(value.get("needs_correction", False))
        return ReplyReview(
            needs_correction=needed,
            correction=str(value.get("correction", "")).strip() if needed else "",
            better_answer=(
                str(value.get("better_answer", "")).strip() if needed else ""
            ),
        )

    def summarize(self, transcript: str) -> dict[str, Any]:
        if not transcript.strip():
            return _empty_summary()
        chunks = _text_chunks(transcript, 22000)
        if len(chunks) == 1:
            return self._summarize_once(chunks[0])
        section_summaries = [
            self._summarize_once(chunk) for chunk in chunks
        ]
        combined = "\n\n".join(
            f"Meeting section {index}:\n{json.dumps(value, ensure_ascii=False)}"
            for index, value in enumerate(section_summaries, 1)
        )
        return self._summarize_once(combined)

    def _summarize_once(self, source: str) -> dict[str, Any]:
        value = self._request(
            (
                "Create a detailed but concise meeting report from the "
                "provided transcript or chronological section summaries. Return "
                "JSON only with summary (string), key_points, decisions, "
                "action_items, and follow_ups (arrays of strings). Preserve "
                "important details and never invent facts absent from the source."
            ),
            source,
            1200,
            "meeting_summary",
            SUMMARY_SCHEMA,
        )
        return {
            "summary": str(value.get("summary", "")).strip(),
            "key_points": _string_list(value.get("key_points")),
            "decisions": _string_list(value.get("decisions")),
            "action_items": _string_list(value.get("action_items")),
            "follow_ups": _string_list(value.get("follow_ups")),
        }

    def _request(
        self,
        instruction: str,
        user_text: str,
        max_tokens: int,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Meeting Mode ke liye Groq API key required hai.")
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.1,
            "max_completion_tokens": max_tokens,
        }
        response_formats = [
            {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            {"type": "json_object"},
            None,
        ]
        last_response = None
        last_parse_error: ValueError | json.JSONDecodeError | None = None
        for response_format in response_formats:
            request = dict(payload)
            if response_format is not None:
                request["response_format"] = response_format
            response = self.client.post(
                "chat/completions",
                json=request,
                timeout=45,
            )
            last_response = response
            if response.status_code == 400:
                continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            try:
                return _parse_json_object(content)
            except (ValueError, json.JSONDecodeError) as exc:
                last_parse_error = exc
        if last_response is not None:
            last_response.raise_for_status()
        raise ValueError(
            "Meeting AI ne valid JSON response nahi diya."
        ) from last_parse_error


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as original_error:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", content):
            try:
                value, _ = decoder.raw_decode(content[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise original_error
    if not isinstance(value, dict):
        raise ValueError("Meeting AI response object nahi tha.")
    return value


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _empty_summary() -> dict[str, Any]:
    return {
        "summary": "No speech was captured in this meeting.",
        "key_points": [],
        "decisions": [],
        "action_items": [],
        "follow_ups": [],
    }


def _text_chunks(text: str, maximum: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in text.splitlines():
        addition = len(line) + 1
        if current and length + addition > maximum:
            chunks.append("\n".join(current))
            current, length = [], 0
        if addition > maximum:
            chunks.extend(
                line[index:index + maximum]
                for index in range(0, len(line), maximum)
            )
            continue
        current.append(line)
        length += addition
    if current:
        chunks.append("\n".join(current))
    return chunks or [text]
