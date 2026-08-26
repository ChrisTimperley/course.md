"""Canvas sync orchestration helpers."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

from coursemd.core.exceptions import CoursemdValidationError
from coursemd.integrations.canvas.assignments import (
    form_for_assignment,
    form_for_participation_event,
)
from coursemd.integrations.canvas.models import (
    CanvasParticipationEvent,
    canvas_assignment_submissions,
    canvas_lab_submission,
    canvas_quiz,
)
from coursemd.integrations.canvas.quizzes import (
    form_for_quiz,
    question_payload_for_canvas,
)
from coursemd.integrations.canvas.rubrics import form_for_rubric

if TYPE_CHECKING:
    from coursemd.core.models.assignment import Assignment
    from coursemd.core.models.lab import Lab
    from coursemd.core.models.quiz import Quiz
    from coursemd.integrations.canvas.config import CanvasParticipationConfig
    from coursemd.integrations.canvas.models import CanvasAssignmentSubmission
    from coursemd.integrations.canvas.resources import AssignmentCanvasClient, QuizCanvasClient

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


def _assignment_group_policy_form(
    group: dict[str, Any],
    policy: CanvasParticipationConfig,
) -> dict[str, Any]:
    form: dict[str, Any] = {}
    if policy.group_weight is not None:
        try:
            current_weight = float(cast("Any", group.get("group_weight")))
        except (TypeError, ValueError):
            current_weight = None
        if current_weight != policy.group_weight:
            form["group_weight"] = policy.group_weight

    if policy.drop_lowest is not None:
        current_rules_raw = group.get("rules")
        current_rules = (
            dict(current_rules_raw) if isinstance(current_rules_raw, dict) else {}
        )
        try:
            current_drop_lowest = int(cast("Any", current_rules.get("drop_lowest")))
        except (TypeError, ValueError):
            current_drop_lowest = None
        if current_drop_lowest != policy.drop_lowest:
            current_rules["drop_lowest"] = policy.drop_lowest
            form["rules"] = json.dumps(current_rules)
    return form


def _apply_assignment_group_policy(
    client: AssignmentCanvasClient,
    course_id: str,
    group: dict[str, Any],
    policy: CanvasParticipationConfig,
    reporter: CanvasSyncReporter | None,
) -> dict[str, Any]:
    form = _assignment_group_policy_form(group, policy)
    if not form:
        return group

    group_id = int(group["id"])
    _emit(
        reporter,
        CanvasSyncEvent(
            action="update",
            target="assignment_group",
            name=policy.assignment_group,
            id=group_id,
            dry_run=client.dry_run,
        ),
    )
    if client.dry_run:
        updated = dict(group)
        if policy.group_weight is not None:
            updated["group_weight"] = policy.group_weight
        if policy.drop_lowest is not None:
            rules = dict(updated.get("rules") or {})
            rules["drop_lowest"] = policy.drop_lowest
            updated["rules"] = rules
        return updated
    return client.update_assignment_group(
        course_id,
        assignment_group_id=group_id,
        form=form,
    )


def _sync_canvas_assignment_submissions(
    client: AssignmentCanvasClient,
    course_id: str,
    canvas_specs: list[CanvasAssignmentSubmission] | list[CanvasParticipationEvent],
    publish_override: bool,
    group_category_id_override: int | None = None,
    reporter: CanvasSyncReporter | None = None,
    site_base_url: str = "",
    assignment_group_policy: CanvasParticipationConfig | None = None,
) -> list[dict[str, Any]]:
    any_group = any(spec.group_assignment for spec in canvas_specs)
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
    configured_groups: set[str] = set()
    for spec in canvas_specs:
        existing: dict[str, Any] | None = None
        if spec.canvas_id is not None:
            existing = assignments_by_id.get(spec.canvas_id)
            if existing is None:
                raise CoursemdValidationError(
                    f"Canvas assignment id {spec.canvas_id} configured for "
                    f"'{spec.name}' was not found in course {course_id}. Refusing to "
                    "match by name or create a replacement; correct or deliberately "
                    "remove the configured Canvas id.",
                    source_path=spec.source_file,
                )
        else:
            existing = assignments_by_name.get(spec.name)
            if existing is None and isinstance(spec, CanvasParticipationEvent):
                existing = assignments_by_name.get(spec.legacy_name)

        assignment_group = spec.canvas_assignment_group or spec.name
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
                group = client.create_assignment_group(
                    course_id,
                    assignment_group,
                    group_weight=(
                        assignment_group_policy.group_weight
                        if assignment_group_policy is not None
                        and assignment_group == assignment_group_policy.assignment_group
                        else None
                    ),
                )
            groups_by_name[assignment_group] = group

        if (
            assignment_group_policy is not None
            and assignment_group == assignment_group_policy.assignment_group
            and assignment_group not in configured_groups
        ):
            group = _apply_assignment_group_policy(
                client,
                course_id,
                group,
                assignment_group_policy,
                reporter,
            )
            groups_by_name[assignment_group] = group
            configured_groups.add(assignment_group)

        group_id = int(group["id"])
        if isinstance(spec, CanvasParticipationEvent):
            form = form_for_participation_event(
                spec,
                group_id,
                publish_override=publish_override,
            )
        else:
            form = form_for_assignment(
                spec,
                group_id,
                publish_override=publish_override,
                group_category_id=group_category_id,
                site_base_url=site_base_url,
            )
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
            elif existing.get("has_submitted_submissions") or client.assignment_has_grades(
                course_id,
                assignment_id,
            ):
                _emit(
                    reporter,
                    CanvasSyncEvent(
                        action="skip",
                        target="assignment",
                        name=spec.name,
                        id=assignment_id,
                        reason="has existing submissions or grades",
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

        result = {
            "action": action,
            "name": spec.name,
            "id": canvas_obj.get("id"),
            "html_url": canvas_obj.get("html_url"),
            "source_file": str(spec.source_file),
        }
        if spec.doc_anchor is not None:
            result["doc_anchor"] = spec.doc_anchor
        results.append(result)

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


def sync_assignments_to_canvas(
    client: AssignmentCanvasClient,
    course_id: str,
    specs: list[Assignment],
    publish_override: bool,
    group_category_id_override: int | None = None,
    reporter: CanvasSyncReporter | None = None,
    site_base_url: str = "",
) -> list[dict[str, Any]]:
    canvas_specs = [
        canvas_spec
        for spec in specs
        for canvas_spec in canvas_assignment_submissions(spec)
    ]
    return _sync_canvas_assignment_submissions(
        client=client,
        course_id=course_id,
        canvas_specs=canvas_specs,
        publish_override=publish_override,
        group_category_id_override=group_category_id_override,
        reporter=reporter,
        site_base_url=site_base_url,
    )


def sync_labs_to_canvas(
    client: AssignmentCanvasClient,
    course_id: str,
    specs: list[Lab],
    publish_override: bool,
    group_category_id_override: int | None = None,
    reporter: CanvasSyncReporter | None = None,
    site_base_url: str = "",
) -> list[dict[str, Any]]:
    """Sync labs as Canvas assignments that accept student submissions."""
    return _sync_canvas_assignment_submissions(
        client=client,
        course_id=course_id,
        canvas_specs=[canvas_lab_submission(spec) for spec in specs],
        publish_override=publish_override,
        group_category_id_override=group_category_id_override,
        reporter=reporter,
        site_base_url=site_base_url,
    )


def sync_participation_to_canvas(
    client: AssignmentCanvasClient,
    course_id: str,
    specs: list[CanvasParticipationEvent],
    policy: CanvasParticipationConfig,
    publish_override: bool,
    reporter: CanvasSyncReporter | None = None,
) -> list[dict[str, Any]]:
    """Sync lecture participation as staff-graded, no-submission assignments."""

    results = _sync_canvas_assignment_submissions(
        client=client,
        course_id=course_id,
        canvas_specs=specs,
        publish_override=publish_override,
        reporter=reporter,
        assignment_group_policy=policy,
    )
    for result, spec in zip(results, specs, strict=True):
        result["event_date"] = spec.event.date.isoformat()
        result["event_title"] = spec.event.title
    return results




def sync_quiz_questions(
    client: QuizCanvasClient,
    course_id: str,
    quiz_id: int,
    spec: Quiz,
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
    specs: list[Quiz],
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
        canvas_data = canvas_quiz(spec.integrations)
        assignment_group = canvas_data.assignment_group or spec.title
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
        if canvas_data.id is not None:
            existing = quizzes_by_id.get(canvas_data.id)
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
