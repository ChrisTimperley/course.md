"""Assignment models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, cast

from coursemd.core.exceptions import validation_error_boundary
from coursemd.core.loaders.assignments import DEFAULT_ASSIGNMENTS_URL_PATH, assignment_link_for
from coursemd.core.loaders.markdown import load_markdown_post
from coursemd.core.loaders.validation import (
    normalize_due_at,
    optional_string,
    require_date,
    require_non_empty_string,
)
from coursemd.core.models.checkpoint import AssignmentCheckpoint
from coursemd.core.models.rubric import Rubric

if TYPE_CHECKING:
    import datetime as dt
    from pathlib import Path


def _parse_integrations(metadata: dict[str, Any]) -> dict[str, Any]:
    integrations_raw = metadata.get("integrations")
    if integrations_raw is None:
        return {}
    if not isinstance(integrations_raw, dict):
        raise TypeError("'integrations' must be an object/map.")
    return dict(cast("dict[str, Any]", integrations_raw))


def _parse_checkpoints(
    value: Any,
    *,
    release_date: dt.date,
    due_date: dt.date,
) -> list[AssignmentCheckpoint]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("'checkpoints' must be a list of objects.")
    return AssignmentCheckpoint.from_list(
        cast("list[dict[str, Any]]", value),
        release_date=release_date,
        due_date=due_date,
    )


def _parse_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "1", "on"}:
            return True
        if text in {"false", "no", "0", "off"}:
            return False
    return bool(value)


def _parse_meta(metadata: dict[str, Any]) -> dict[str, Any]:
    meta_raw = metadata.get("meta")
    if meta_raw is None:
        meta: dict[str, Any] = {}
    elif isinstance(meta_raw, dict):
        meta = dict(cast("dict[str, Any]", meta_raw))
    else:
        raise TypeError("'meta' must be an object/map.")

    if metadata.get("grading") is not None:
        meta["grading"] = metadata["grading"]
    return meta


def _parse_card(metadata: dict[str, Any]) -> dict[str, Any]:
    card_raw = metadata.get("card")
    if card_raw is None:
        return {}
    if not isinstance(card_raw, dict):
        raise TypeError("'card' must be an object/map.")
    return dict(cast("dict[str, Any]", card_raw))


def _parse_rubric(value: dict[str, Any]) -> Rubric:
    return Rubric.from_metadata(value)


@dataclass(frozen=True)
class Assignment:
    """Canonical homework/assignment page specification."""

    source_file: Path
    title: str
    release_date: dt.date
    due_date: dt.date
    link: str
    due_at: str | None = None
    kind: str = "assignment"
    description: str | None = None
    summary: str | None = None
    card: dict[str, Any] = field(default_factory=dict)
    reveal_date: dt.date | None = None
    group_assignment: bool = False
    rubric: Rubric = field(default_factory=lambda: Rubric(sections=[]))
    checkpoints: list[AssignmentCheckpoint] = field(default_factory=list)
    doc_url: str | None = None
    doc_anchor: str | None = None
    notes: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    integrations: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.title

    @property
    def reveal_on(self) -> dt.date:
        return self.reveal_date or self.release_date

    def with_assignment_url_path(self, assignment_url_path: str) -> Assignment:
        return replace(
            self,
            link=assignment_link_for(
                self.source_file,
                assignment_url_path=assignment_url_path,
            ),
        )

    @classmethod
    def load(cls, filename: Path) -> Assignment:
        """Load a single assignment from a Markdown file."""

        with validation_error_boundary(filename):
            post = load_markdown_post(filename)
            metadata = post.metadata

            title = require_non_empty_string(metadata.get("title"), "title")
            release_date = require_date(metadata.get("release_date"), "release_date")

            due_date_raw = metadata.get("due_date")
            due_at_raw = metadata.get("due_at")
            due_at = None if due_at_raw is None else normalize_due_at(due_at_raw, title)
            due_date_from_due_at = None if due_at is None else require_date(due_at, "due_at")

            if due_date_raw is None and due_date_from_due_at is None:
                raise ValueError("assignment must define 'due_date' or 'due_at'.")

            if due_date_raw is None:
                if due_date_from_due_at is None:
                    raise ValueError("assignment must define 'due_date' or 'due_at'.")
                due_date = due_date_from_due_at
            else:
                due_date = require_date(due_date_raw, "due_date")
            if due_date_from_due_at is not None and due_date != due_date_from_due_at:
                raise ValueError("'due_date' must match the calendar date of 'due_at'.")
            if due_date < release_date:
                raise ValueError("'due_date' must not be earlier than 'release_date'.")

            reveal_date = None
            if metadata.get("reveal_date") is not None:
                reveal_date = require_date(metadata.get("reveal_date"), "reveal_date")
                if reveal_date > due_date:
                    raise ValueError("'reveal_date' must not be later than 'due_date'.")

            return cls(
                source_file=filename,
                title=title,
                release_date=release_date,
                due_date=due_date,
                link=assignment_link_for(
                    filename,
                    assignment_url_path=DEFAULT_ASSIGNMENTS_URL_PATH,
                ),
                due_at=due_at,
                kind=optional_string(metadata.get("kind")) or "assignment",
                description=str(post.content).strip() or None,
                summary=optional_string(metadata.get("summary")),
                card=_parse_card(metadata),
                reveal_date=reveal_date,
                group_assignment=_parse_bool(metadata.get("group_assignment")),
                rubric=_parse_rubric(metadata),
                checkpoints=_parse_checkpoints(
                    metadata.get("checkpoints"),
                    release_date=release_date,
                    due_date=due_date,
                ),
                doc_url=optional_string(metadata.get("doc_url")),
                doc_anchor=optional_string(metadata.get("doc_anchor")),
                notes=optional_string(metadata.get("notes")),
                meta=_parse_meta(metadata),
                integrations=_parse_integrations(metadata),
            )


__all__ = (
    "Assignment",
    "AssignmentCheckpoint",
)
