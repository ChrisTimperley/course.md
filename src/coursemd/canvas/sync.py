"""Canvas sync orchestration helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from coursemd.canvas.assignments import form_for_assignment
from coursemd.canvas.quizzes import form_for_quiz, question_payload_for_canvas
from coursemd.canvas.resources import AssignmentCanvasClient, QuizCanvasClient
from coursemd.canvas.rubrics import form_for_rubric
from coursemd.core.models.assignment import AssignmentSpec
from coursemd.core.models.quiz import QuizSpec

CanvasSyncAction = Literal["create", "delete", "skip", "sync", "update"]
CanvasSyncTarget = Literal["assignment", "assignment_group", "quiz", "quiz_question", "rubric"]
CanvasSyncReporter = Callable[["CanvasSyncEvent"], None]


@dataclass(frozen=True)
class CanvasSyncEvent:
    action: CanvasSyncAction
    target: CanvasSyncTarget
    name: str | None = None
    id: int | None = None
    dry_run: bool = False
    reason: str | None = None
    count: int | None = None


def _emit(reporter: CanvasSyncReporter | None, event: CanvasSyncEvent) -> None:
    if reporter is not None:
        reporter(event)


def resolve_group_category_id(
    client: AssignmentCanvasClient,
    course_id: str,
    group_category_id_override: int | None = None,
) -> int | None:
    if group_category_id_override is not None:
        return group_category_id_override

    categories = client.get_paginated(
        f"/courses/{course_id}/group_categories",
        params={"per_page": 100},
    )
    for category in categories:
        if category.get("role") not in ("communities", "student_organized"):
            return int(category["id"])
    return int(categories[0]["id"]) if categories else None


def sync_assignments_to_canvas(
    client: AssignmentCanvasClient,
    course_id: str,
    specs: list[AssignmentSpec],
    publish_override: bool,
    group_category_id_override: int | None = None,
    reporter: CanvasSyncReporter | None = None,
) -> list[dict[str, Any]]:
    any_group = any(spec.group_assignment for spec in specs)
    group_category_id: int | None = None
    if any_group:
        group_category_id = resolve_group_category_id(client, course_id, group_category_id_override)
        if group_category_id is None:
            raise SystemExit(
                "group_assignment is true but no group category found. "
                "Create a group set in Canvas or set CANVAS_GROUP_CATEGORY_ID."
            )

    groups = client.get_paginated(
        f"/courses/{course_id}/assignment_groups",
        params={"per_page": 100},
    )
    groups_by_name = {str(group.get("name")): group for group in groups}

    assignments = client.get_paginated(
        f"/courses/{course_id}/assignments",
        params={"per_page": 100},
    )
    assignments_by_name: dict[str, dict[str, Any]] = {}
    assignments_by_id: dict[int, dict[str, Any]] = {}
    for assignment in assignments:
        name = str(assignment.get("name"))
        assignment_id = assignment.get("id")
        if name not in assignments_by_name:
            assignments_by_name[name] = assignment
        if assignment_id is not None:
            assignments_by_id[int(assignment_id)] = assignment

    results: list[dict[str, Any]] = []
    for spec in specs:
        assignment_group = spec.integrations.canvas.assignment_group or spec.name
        group = groups_by_name.get(assignment_group)
        if group is None:
            _emit(
                reporter,
                CanvasSyncEvent(
                    action="create",
                    target="assignment_group",
                    name=assignment_group,
                    dry_run=client.dry_run,
                ),
            )
            if client.dry_run:
                group = {"id": -1, "name": assignment_group}
            else:
                group = client.create_assignment_group(course_id, assignment_group)
            groups_by_name[assignment_group] = group

        group_id = int(group["id"])
        form = form_for_assignment(
            spec,
            group_id,
            publish_override=publish_override,
            group_category_id=group_category_id,
        )
        existing: dict[str, Any] | None = None
        if spec.integrations.canvas.id is not None:
            existing = assignments_by_id.get(spec.integrations.canvas.id)
        if existing is None:
            existing = assignments_by_name.get(spec.name)

        if existing is None:
            action = "create"
            _emit(
                reporter,
                CanvasSyncEvent(
                    action="create",
                    target="assignment",
                    name=spec.name,
                    dry_run=client.dry_run,
                ),
            )
            if client.dry_run:
                canvas_obj: dict[str, Any] = {"id": None, "html_url": None}
            else:
                canvas_obj = client.create_assignment(course_id, form=form)
                assignments_by_name[spec.name] = canvas_obj
        else:
            assignment_id = int(existing["id"])
            is_released = client.is_assignment_released(course_id, assignment_id)

            if is_released:
                _emit(
                    reporter,
                    CanvasSyncEvent(
                        action="skip",
                        target="assignment",
                        name=spec.name,
                        id=assignment_id,
                        reason="is currently released",
                    ),
                )
                canvas_obj = existing
                action = "skipped"
            else:
                action = "update"
                _emit(
                    reporter,
                    CanvasSyncEvent(
                        action="update",
                        target="assignment",
                        name=spec.name,
                        id=assignment_id,
                        dry_run=client.dry_run,
                    ),
                )
                if client.dry_run:
                    canvas_obj = existing
                else:
                    canvas_obj = client.update_assignment(
                        course_id,
                        assignment_id=assignment_id,
                        form=form,
                    )
                    assignments_by_name[spec.name] = canvas_obj

        results.append(
            {
                "action": action,
                "name": spec.name,
                "id": canvas_obj.get("id"),
                "html_url": canvas_obj.get("html_url"),
                "source_file": str(spec.source_file),
            }
        )

        if action != "skipped" and spec.rubric_criteria and canvas_obj.get("id") is not None:
            assignment_id = int(canvas_obj["id"])
            _emit(
                reporter,
                CanvasSyncEvent(
                    action="sync",
                    target="rubric",
                    name=spec.name,
                    id=assignment_id,
                    dry_run=client.dry_run,
                    count=len(spec.rubric_criteria),
                ),
            )
            if not client.dry_run:
                client.create_rubric(
                    course_id=course_id,
                    form=form_for_rubric(
                        assignment_id=assignment_id,
                        criteria=spec.rubric_criteria,
                        title=spec.name,
                    ),
                )

    return results


__all__ = [
    "CanvasSyncEvent",
    "CanvasSyncReporter",
    "resolve_group_category_id",
    "sync_assignments_to_canvas",
    "sync_quiz_questions",
    "sync_quizzes_to_canvas",
]


def sync_quiz_questions(
    client: QuizCanvasClient,
    course_id: str,
    quiz_id: int,
    spec: QuizSpec,
    reporter: CanvasSyncReporter | None = None,
) -> None:
    existing = client.list_quiz_questions(course_id, quiz_id)
    for question in existing:
        question_id = question.get("id")
        if question_id is not None:
            try:
                parsed_question_id = int(question_id)
                _emit(
                    reporter,
                    CanvasSyncEvent(
                        action="delete",
                        target="quiz_question",
                        id=parsed_question_id,
                    ),
                )
                client.delete_quiz_question(course_id, quiz_id, parsed_question_id)
            except (TypeError, ValueError):
                pass

    for question_spec in spec.questions:
        payload = question_payload_for_canvas(question_spec, spec.source_file)
        _emit(
            reporter,
            CanvasSyncEvent(
                action="create",
                target="quiz_question",
                name=f"Q{question_spec.position}: {question_spec.question_text[:50]}...",
            ),
        )
        client.create_quiz_question(course_id, quiz_id, payload)


def sync_quizzes_to_canvas(
    client: QuizCanvasClient,
    course_id: str,
    specs: list[QuizSpec],
    publish_override: bool,
    skip_if_submissions: bool = True,
    reporter: CanvasSyncReporter | None = None,
) -> list[dict[str, Any]]:
    groups = client.get_paginated(
        f"/courses/{course_id}/assignment_groups",
        params={"per_page": 100},
    )
    groups_by_name = {str(group.get("name")): group for group in groups}

    quizzes = client.get_paginated(
        f"/courses/{course_id}/quizzes",
        params={"per_page": 100},
    )
    quizzes_by_id: dict[int, dict[str, Any]] = {}
    quizzes_by_title: dict[str, dict[str, Any]] = {}
    for quiz in quizzes:
        quiz_id = quiz.get("id")
        title = str(quiz.get("title", ""))
        if quiz_id is not None:
            quizzes_by_id[int(quiz_id)] = quiz
        if title:
            quizzes_by_title[title] = quiz

    results: list[dict[str, Any]] = []
    for spec in specs:
        assignment_group = spec.integrations.canvas.assignment_group or spec.title
        group = groups_by_name.get(assignment_group)
        if group is None:
            _emit(
                reporter,
                CanvasSyncEvent(
                    action="create",
                    target="assignment_group",
                    name=assignment_group,
                    dry_run=client.dry_run,
                ),
            )
            if client.dry_run:
                group = {"id": -1, "name": assignment_group}
            else:
                group = client.create_assignment_group(course_id, assignment_group)
            groups_by_name[assignment_group] = group

        group_id = int(group["id"])
        form = form_for_quiz(spec, group_id, publish_override)

        existing: dict[str, Any] | None = None
        if spec.integrations.canvas.id is not None:
            existing = quizzes_by_id.get(spec.integrations.canvas.id)
        if existing is None:
            existing = quizzes_by_title.get(spec.title)

        existing_quiz_id: int | None = None
        if existing is None:
            action = "create"
            _emit(
                reporter,
                CanvasSyncEvent(
                    action="create",
                    target="quiz",
                    name=spec.title,
                    dry_run=client.dry_run,
                ),
            )
            if client.dry_run:
                quiz_obj: dict[str, Any] = {"id": None, "html_url": None}
            else:
                quiz_obj = client.create_quiz(course_id, form=form)
                quizzes_by_title[spec.title] = quiz_obj
        else:
            action = "update"
            existing_quiz_id = int(existing["id"])
            if client.dry_run:
                _emit(
                    reporter,
                    CanvasSyncEvent(
                        action="update",
                        target="quiz",
                        name=spec.title,
                        id=existing_quiz_id,
                        dry_run=True,
                    ),
                )
                quiz_obj = existing
            else:
                has_submissions = client.quiz_has_submissions(course_id, existing_quiz_id)
                is_released = client.is_quiz_released(course_id, existing_quiz_id)

                if (skip_if_submissions and has_submissions) or is_released:
                    reasons = []
                    if skip_if_submissions and has_submissions:
                        reasons.append("has submissions")
                    if is_released:
                        reasons.append("is currently released")
                    reason_str = " and ".join(reasons)

                    _emit(
                        reporter,
                        CanvasSyncEvent(
                            action="skip",
                            target="quiz",
                            name=spec.title,
                            id=existing_quiz_id,
                            reason=reason_str,
                        ),
                    )
                    quiz_obj = existing
                    action = "skipped"
                else:
                    _emit(
                        reporter,
                        CanvasSyncEvent(
                            action="update",
                            target="quiz",
                            name=spec.title,
                            id=existing_quiz_id,
                        ),
                    )
                    quiz_obj = client.update_quiz(
                        course_id,
                        quiz_id=existing_quiz_id,
                        form=form,
                    )
                quizzes_by_title[spec.title] = quiz_obj

        canvas_quiz_id = quiz_obj.get("id")
        if action == "update":
            sync_quiz_id = existing_quiz_id
        else:
            try:
                sync_quiz_id = int(canvas_quiz_id) if canvas_quiz_id is not None else None
            except (TypeError, ValueError):
                sync_quiz_id = None
        if sync_quiz_id is not None and not client.dry_run and action != "skipped":
            sync_quiz_questions(client, course_id, sync_quiz_id, spec, reporter=reporter)
            quiz_obj = client.update_quiz(course_id, sync_quiz_id, form)

        results.append(
            {
                "action": action,
                "title": spec.title,
                "id": canvas_quiz_id,
                "html_url": quiz_obj.get("html_url"),
                "source_file": str(spec.source_file),
            }
        )

    return results
