"""Lab models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, cast

from coursemd.core.exceptions import validation_error_boundary
from coursemd.core.loaders.markdown import load_markdown_post
from coursemd.core.loaders.validation import optional_string, require_date, require_non_empty_string
from coursemd.core.models.course_event import CourseEvent

if TYPE_CHECKING:
    import datetime as dt
    from pathlib import Path

    from coursemd.core.config import CourseConfig


DEFAULT_LABS_URL_PATH = "labs"


def _parse_card(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return optional presentation metadata for a lab."""
    card_raw = metadata.get("card")
    if card_raw is None:
        return {}
    if not isinstance(card_raw, dict):
        raise TypeError("'card' must be an object/map.")
    return dict(cast("dict[str, Any]", card_raw))


@dataclass(frozen=True)
class Lab:
    """A lab session page specification."""

    source_file: Path
    title: str
    date: dt.date
    link: str
    description: str | None = None
    card: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.title

    def with_labs_url_path(self, labs_url_path: str) -> Lab:
        return replace(
            self,
            link=f"/{labs_url_path.strip('/')}/{self.source_file.stem}/",
        )

    def as_course_event(self) -> CourseEvent:
        """Return the lab as an event for inclusion in a course schedule."""
        return CourseEvent(kind="lab", date=self.date, title=self.title, link=self.link)

    @classmethod
    def load(cls, filename: Path) -> Lab | None:
        """Load a single lab from a Markdown file, or None if kind != 'lab'."""

        with validation_error_boundary(filename):
            post = load_markdown_post(filename)
            metadata: dict[str, Any] = post.metadata

            if str(metadata.get("kind", "")).strip().lower() != "lab":
                return None

            title = require_non_empty_string(metadata.get("title"), "title")
            date = require_date(metadata.get("date"), "date")
            description = optional_string(metadata.get("description"))

            return cls(
                source_file=filename,
                title=title,
                date=date,
                link=f"/{DEFAULT_LABS_URL_PATH}/{filename.stem}/",
                description=description,
                card=_parse_card(metadata),
            )

    @classmethod
    def find(
        cls,
        config: CourseConfig,
        path: Path | None = None,
    ) -> list[Lab]:
        """Discover and load all labs from a directory."""
        directory = path if path is not None else config.paths.labs_dir
        if not directory.is_dir():
            return []
        files = sorted(p for p in directory.glob("*.md") if p.name != "index.md")
        labs = [lab for f in files if (lab := cls.load(f)) is not None]
        return sorted(labs, key=lambda lab: lab.date)
