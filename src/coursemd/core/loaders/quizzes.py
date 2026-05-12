"""Quiz frontmatter loaders."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def default_quiz_files(repo_root: Path) -> list[Path]:
    quizzes_dir = repo_root / "website" / "docs" / "quizzes"
    if not quizzes_dir.exists():
        return []
    return sorted(path for path in quizzes_dir.glob("*.md") if path.name != "index.md")
