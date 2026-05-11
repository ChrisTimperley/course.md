"""Helpers for persisting Canvas IDs back into Markdown frontmatter."""

from __future__ import annotations

from pathlib import Path

import frontmatter  # type: ignore[import-untyped]

from coursemd.core.loaders.markdown import load_markdown_post


def _canvas_id_as_int(value: object) -> int:
    return int(str(value))


def update_assignment_frontmatter_with_ids(results: list[dict[str, object]]) -> None:
    by_file: dict[Path, list[dict[str, object]]] = {}
    for result in results:
        canvas_id = result.get("id")
        if canvas_id is None:
            continue
        path = Path(str(result["source_file"]))
        by_file.setdefault(path, []).append(result)

    for path, file_results in by_file.items():
        post = load_markdown_post(path)
        integrations = post.metadata.setdefault("integrations", {})
        if not isinstance(integrations, dict):
            continue
        canvas = integrations.setdefault("canvas", {})
        if not isinstance(canvas, dict):
            continue
        changed = False
        for result in file_results:
            canvas_id = _canvas_id_as_int(result["id"])
            doc_anchor = str(result.get("doc_anchor") or "").strip()
            if doc_anchor:
                checkpoints = canvas.setdefault("checkpoints", [])
                if not isinstance(checkpoints, list):
                    continue
                for checkpoint in checkpoints:
                    if not isinstance(checkpoint, dict):
                        continue
                    if checkpoint.get("doc_anchor") != doc_anchor:
                        continue
                    if checkpoint.get("canvas_id") == canvas_id:
                        break
                    checkpoint["canvas_id"] = canvas_id
                    changed = True
                    print(
                        f"Updated {path} integrations.canvas.checkpoints "
                        f"{doc_anchor} canvas_id={canvas_id}"
                    )
                    break
                continue

            if canvas.get("id") == canvas_id:
                continue
            canvas["id"] = canvas_id
            changed = True
            print(f"Updated {path} with integrations.canvas.id={canvas_id}")
        if changed:
            path.write_text(frontmatter.dumps(post), encoding="utf-8")


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
