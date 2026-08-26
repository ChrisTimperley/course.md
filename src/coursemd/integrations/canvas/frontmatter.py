"""Helpers for persisting Canvas IDs back into Markdown frontmatter."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, cast

import frontmatter  # type: ignore[import-untyped]
import yaml  # type: ignore[import-untyped]

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


def update_lab_frontmatter_with_ids(results: list[dict[str, object]]) -> None:
    """Persist Canvas assignment IDs for synced labs."""
    update_assignment_frontmatter_with_ids(results)


def update_course_config_with_participation_ids(
    results: list[dict[str, object]],
) -> None:
    """Persist Canvas participation IDs on their source lecture events."""

    by_file: dict[Path, dict[tuple[str, str], int]] = {}
    for result in results:
        canvas_id = result.get("id")
        event_date = str(result.get("event_date") or "").strip()
        event_title = str(result.get("event_title") or "").strip()
        if canvas_id is None or not event_date or not event_title:
            continue
        path = Path(str(result["source_file"]))
        by_file.setdefault(path, {})[(event_date, event_title)] = _canvas_id_as_int(canvas_id)

    for path, ids_by_event in by_file.items():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            continue
        config = cast("dict[str, Any]", loaded)
        schedule = config.get("schedule")
        if not isinstance(schedule, dict):
            continue
        events = schedule.get("events")
        if not isinstance(events, list):
            continue

        changed = False
        for event_raw in cast("list[Any]", events):
            if not isinstance(event_raw, dict):
                continue
            event = cast("dict[str, Any]", event_raw)
            date_raw = event.get("date")
            event_date = date_raw.isoformat() if isinstance(date_raw, dt.date) else str(date_raw)
            event_title = str(event.get("title") or "").strip()
            canvas_id = ids_by_event.get((event_date, event_title))
            if canvas_id is None:
                continue
            integrations = event.setdefault("integrations", {})
            if not isinstance(integrations, dict):
                continue
            canvas = integrations.setdefault("canvas", {})
            if not isinstance(canvas, dict) or canvas.get("participation_id") == canvas_id:
                continue
            canvas["participation_id"] = canvas_id
            changed = True
            print(
                f"Updated {path} lecture {event_date} with "
                f"integrations.canvas.participation_id={canvas_id}"
            )

        if changed:
            path.write_text(
                yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )


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
