"""Staff models for course repositories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from coursemd.core.exceptions import CoursemdValidationError


def _require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CoursemdValidationError(f"{label} must be a non-empty string.")
    return value.strip()


def _optional_string(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, label=label)


@dataclass(frozen=True)
class StaffMember:
    """Represents a member of the course staff."""

    name: str
    role: str
    email: str | None = None
    website: str | None = None
    photo: str | None = None
    github: str | None = None
    teams: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: Any, *, label: str = "staff member") -> Self:
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise CoursemdValidationError(f"{label} must be a mapping.")
        return cls.from_dict(value, label=label)

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, label: str = "staff member") -> Self:
        teams_raw = value.get("teams", [])
        if teams_raw is None:
            teams_raw = []
        if not isinstance(teams_raw, list):
            raise CoursemdValidationError(f"{label}.teams must be a list.")

        teams: list[str] = []
        for index, team in enumerate(teams_raw):
            if team is None or isinstance(team, bool):
                raise CoursemdValidationError(f"{label}.teams[{index}] must be a non-empty value.")
            team_name = str(team).strip()
            if not team_name:
                raise CoursemdValidationError(f"{label}.teams[{index}] must be a non-empty value.")
            teams.append(team_name)

        return cls(
            name=_require_string(value.get("name"), label=f"{label}.name"),
            role=_require_string(value.get("role"), label=f"{label}.role").lower(),
            email=_optional_string(value.get("email"), label=f"{label}.email"),
            website=_optional_string(value.get("website"), label=f"{label}.website"),
            photo=_optional_string(value.get("photo"), label=f"{label}.photo"),
            github=_optional_string(value.get("github"), label=f"{label}.github"),
            teams=tuple(teams),
        )

    @classmethod
    def from_list(cls, value: Any) -> list[Self]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise CoursemdValidationError("staff must be a list.")
        return [cls.parse(item, label=f"staff[{index}]") for index, item in enumerate(value)]
