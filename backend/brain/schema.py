from __future__ import annotations

from typing import Any

from ..agent.catalog import ACTION_NAMES, PARAMETER_KEYS


def intent_schema(max_actions: int = 5) -> dict[str, Any]:
    parameter_properties = {
        key: {"type": ["string", "number", "boolean", "null"]}
        for key in PARAMETER_KEYS
    }
    return {
        "type": "object",
        "properties": {
            "spoken_reply": {"type": "string"},
            "needs_clarification": {"type": "boolean"},
            "actions": {
                "type": "array",
                "maxItems": max(1, min(10, int(max_actions))),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": list(ACTION_NAMES)},
                        "parameters": {
                            "type": "object",
                            "properties": parameter_properties,
                            "required": list(PARAMETER_KEYS),
                            "additionalProperties": False,
                        },
                    },
                    "required": ["name", "parameters"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["spoken_reply", "needs_clarification", "actions"],
        "additionalProperties": False,
    }
