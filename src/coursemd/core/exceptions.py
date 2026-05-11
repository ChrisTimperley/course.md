"""Core exception types for coursemd validation and loading."""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from inspect import Signature, signature
from pathlib import Path
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

P = ParamSpec("P")
T = TypeVar("T")
SOURCE_PATH_PARAM_NAMES = ("source_file", "filename", "path", "config_path", "source_path")


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


def _source_path_for_call(
    func_signature: Signature,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> Path | None:
    try:
        bound_arguments = func_signature.bind_partial(*args, **kwargs)
    except TypeError:
        return None

    for name in SOURCE_PATH_PARAM_NAMES:
        value = bound_arguments.arguments.get(name)
        if isinstance(value, Path):
            return value

    return None


@contextmanager
def validation_error_boundary(source_path: Path | None) -> Iterator[None]:
    """Attach a source path to validation errors raised within a block."""

    try:
        yield
    except CoursemdValidationError as exc:
        if source_path is not None and exc.source_path is None:
            raise CoursemdValidationError(exc.message, source_path=source_path) from exc
        raise
    except (TypeError, ValueError) as exc:
        raise CoursemdValidationError(str(exc), source_path=source_path) from exc


def wrap_validation_errors(func: Callable[P, T]) -> Callable[P, T]:
    """Convert generic parsing exceptions into CoursemdValidationError."""

    func_signature = signature(func)

    @wraps(func)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        source_path = _source_path_for_call(func_signature, args, kwargs)
        with validation_error_boundary(source_path):
            return func(*args, **kwargs)

    return wrapped
