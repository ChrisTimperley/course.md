"""Helpers for persisting Canvas IDs back into Markdown frontmatter."""

from __future__ import annotations

from pathlib import Path

import frontmatter  # type: ignore[import-untyped]

from coursemd.core.loaders.markdown import load_markdown_post


def _canvas_id_as_int(value: object) -> int:
    return int(str(value))


def update_assignment_frontmatter_with_ids(results: list[dict[str, object]]) -> None:
    by_file: dict[Path, int] = {}
    for result in results:
        canvas_id = result.get("id")
        if canvas_id is None:
            continue
        path = Path(str(result["source_file"]))
        by_file[path] = _canvas_id_as_int(canvas_id)

    for path, canvas_id in by_file.items():
        post = load_markdown_post(path)
        integrations = post.metadata.setdefault("integrations", {})
        if not isinstance(integrations, dict):
            continue
        canvas = integrations.setdefault("canvas", {})
        if not isinstance(canvas, dict):
            continue
        if canvas.get("id") == canvas_id:
            continue
        canvas["id"] = canvas_id
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
        print(f"Updated {path} with integrations.canvas.id={canvas_id}")


def update_quiz_frontmatter_with_canvas_id(results: list[dict[str, object]]) -> None:
    for result in results:
        canvas_id = result.get("id")
        if canvas_id is None:
            continue
        path = Path(str(result["source_file"]))
        post = load_markdown_post(path)
        canvas_id_int = _canvas_id_as_int(canvas_id)
        integrations = post.metadata.setdefault("integrations", {})
        if not isinstance(integrations, dict):
            continue
        canvas = integrations.setdefault("canvas", {})
        if not isinstance(canvas, dict):
            continue
        if canvas.get("id") == canvas_id_int:
            continue
        canvas["id"] = canvas_id_int
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
        print(f"Updated {path} with integrations.canvas.id={canvas_id}")
