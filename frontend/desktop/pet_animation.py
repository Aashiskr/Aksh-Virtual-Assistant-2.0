from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageTk


STATE_EXPRESSIONS = {
    "awake": "happy",
    "busy": "working",
    "enrolling": "working",
    "error": "error",
    "friends": "happy",
    "idle": "idle",
    "listening": "listening",
    "locked": "error",
    "offline": "error",
    "permission": "thinking",
    "setup": "thinking",
    "sleeping": "sleeping",
    "thinking": "thinking",
    "working": "working",
}


def expression_for_state(state: str, tick: int) -> str:
    expression = STATE_EXPRESSIONS.get(state, "idle")
    if expression != "idle":
        return expression
    phase = tick % 140
    if 92 <= phase < 102:
        return "thinking"
    if 120 <= phase < 134:
        return "happy"
    return "idle"


def motion_for_state(state: str, tick: int) -> tuple[int, int, int]:
    """Returns scale delta, vertical offset, and rotation degrees."""
    if state == "listening":
        sequence = ((0, 0, -1), (2, -2, 0), (0, -1, 1), (-1, 0, 0))
    elif state in {"working", "busy", "enrolling"}:
        sequence = ((0, 0, 0), (3, -2, -1), (1, -1, 0), (3, -2, 1))
    elif state == "thinking":
        sequence = ((0, 0, -1), (0, -1, -2), (0, -1, -1), (0, 0, 0))
    elif state == "sleeping":
        sequence = ((-2, 1, 0), (-1, 2, 0), (-2, 2, 0), (-1, 1, 0))
    elif state in {"locked", "error", "offline"}:
        sequence = ((-1, 1, -1), (-1, 2, -1), (0, 1, 0), (-1, 2, 0))
    else:
        sequence = ((0, 0, 0), (1, -1, 0), (0, 0, 0), (-1, 1, 0))
    return sequence[(tick // 2) % len(sequence)]


class PetAnimator:
    def __init__(self, idle_path: Path, size: int):
        expression_dir = idle_path.parent / "expressions"
        self.paths = {
            "idle": idle_path,
            **{
                name: expression_dir / f"aksh_{name}.png"
                for name in (
                    "listening",
                    "thinking",
                    "working",
                    "happy",
                    "error",
                    "sleeping",
                )
            },
        }
        self.sources = self._load_sources()
        self.size = int(size)
        self.tick = 0
        self.state = "idle"
        self.reaction: tuple[str, int] | None = None
        self._cache: dict[tuple[str, int, int], ImageTk.PhotoImage] = {}

    def _load_sources(self) -> dict[str, Image.Image]:
        idle = Image.open(self.paths["idle"]).convert("RGBA")
        sources = {"idle": idle}
        for name, path in self.paths.items():
            if name != "idle" and path.exists():
                sources[name] = Image.open(path).convert("RGBA")
        return sources

    def set_size(self, size: int) -> None:
        self.size = int(size)
        self._cache.clear()

    def set_state(self, state: str) -> None:
        if state == self.state:
            return
        self.state = state
        self.tick = 0
        self.reaction = None

    def react(self, expression: str, duration_ticks: int) -> None:
        if expression in self.sources:
            self.reaction = (expression, max(1, int(duration_ticks)))

    def next_frame(self, state: str) -> tuple[ImageTk.PhotoImage, int]:
        self.set_state(state)
        expression = self._current_expression()
        scale_delta, offset_y, rotation = motion_for_state(state, self.tick)
        photo = self._photo(expression, scale_delta, rotation)
        self.tick += 1
        if self.reaction:
            name, remaining = self.reaction
            self.reaction = (
                (name, remaining - 1) if remaining > 1 else None
            )
        return photo, offset_y

    def _current_expression(self) -> str:
        if self.reaction:
            return self.reaction[0]
        desired = expression_for_state(self.state, self.tick)
        return desired if desired in self.sources else "idle"

    def _photo(
        self,
        expression: str,
        scale_delta: int,
        rotation: int,
    ) -> ImageTk.PhotoImage:
        key = (expression, scale_delta, rotation)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        source = self.sources.get(expression, self.sources["idle"]).copy()
        target = max(32, self.size - 10 + scale_delta)
        source.thumbnail((target, target), Image.Resampling.LANCZOS)
        frame = Image.new("RGBA", (self.size, self.size))
        x = (self.size - source.width) // 2
        y = (self.size - source.height) // 2
        frame.alpha_composite(source, (x, y))
        if rotation:
            frame = frame.rotate(
                rotation,
                resample=Image.Resampling.BICUBIC,
                expand=False,
            )
        photo = ImageTk.PhotoImage(frame)
        self._cache[key] = photo
        return photo
