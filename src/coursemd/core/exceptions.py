"""Core exception types for coursemd validation and loading."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

P = ParamSpec("P")
T = TypeVar("T")


class CoursemdError(Exception):
    """Base exception for coursemd-specific errors."""


class CoursemdValidationError(CoursemdError):
    """Validation or parsing error raised by the core loading pipeline."""

    def __init__(self, message: str, *, source_path: Path | None = None) -> None:
        self.message = message
        self.source_path = source_path
        super().__init__(str(self))

    def __str__(self) -> str:
        if self.source_path is None:
            return self.message
        return f"{self.source_path}: {self.message}"


def wrap_validation_errors(func: Callable[P, T]) -> Callable[P, T]:
    """Convert generic parsing exceptions into CoursemdValidationError."""

    @wraps(func)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except CoursemdValidationError:
            raise
        except (TypeError, ValueError) as exc:
            raise CoursemdValidationError(str(exc)) from exc

    return wrapped
