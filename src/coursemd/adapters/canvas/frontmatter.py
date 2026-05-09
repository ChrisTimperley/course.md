"""Helpers for persisting Canvas IDs back into Markdown frontmatter."""

from __future__ import annotations

from pathlib import Path

import frontmatter  # type: ignore[import-untyped]

from coursemd.loaders.markdown import load_markdown_post


def _canvas_id_as_int(value: object) -> int:
    return int(str(value))


def update_assignment_frontmatter_with_ids(results: list[dict[str, object]]) -> None:
    by_file: dict[Path, list[dict[str, object]]] = {}
    for result in results:
        canvas_id = result.get("id")
        if canvas_id is None:
            continue
        path = Path(str(result["source_file"]))
        by_file.setdefault(path, []).append({"name": result["name"], "id": canvas_id})

    for path, updates in by_file.items():
        post = load_markdown_post(path)
        assignments = post.metadata.get("assignments")
        if not isinstance(assignments, list):
            continue

        updated_names: list[str] = []
        for item in assignments:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            integrations = item.setdefault("integrations", {})
            if not isinstance(integrations, dict):
                continue
            canvas = integrations.setdefault("canvas", {})
            if not isinstance(canvas, dict):
                continue
            if "id" in canvas:
                continue
            for update in updates:
                if update["name"] == name:
                    canvas["id"] = _canvas_id_as_int(update["id"])
                    updated_names.append(name)
                    break

        if updated_names:
            path.write_text(frontmatter.dumps(post), encoding="utf-8")
            print(f"Updated {path} with integrations.canvas.id for: {', '.join(updated_names)}")


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
