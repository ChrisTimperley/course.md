"""Canvas resource clients used by sync workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from coursemd.canvas.client import CanvasApiClient


def _published_item_is_released(data: dict[str, Any]) -> bool:
    if not data.get("published", False):
        return False

    unlock_at_str = data.get("unlock_at")
    if unlock_at_str:
        try:
            unlock_at_dt = datetime.fromisoformat(str(unlock_at_str).replace("Z", "+00:00"))
            if unlock_at_dt > datetime.now(UTC):
                return False
        except ValueError:
            pass

    return True


class AssignmentCanvasClient(CanvasApiClient):
    def create_assignment_group(self, course_id: str, name: str) -> dict[str, Any]:
        response = self.session.post(
            self._api_url(f"/courses/{course_id}/assignment_groups"),
            data={"name": name},
        )
        self._raise_for_status(response)
        return cast("dict[str, Any]", response.json())

    def create_assignment(self, course_id: str, form: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            self._api_url(f"/courses/{course_id}/assignments"),
            data=form,
        )
        self._raise_for_status(response)
        return cast("dict[str, Any]", response.json())

    def update_assignment(
        self,
        course_id: str,
        assignment_id: int,
        form: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.session.put(
            self._api_url(f"/courses/{course_id}/assignments/{assignment_id}"),
            data=form,
        )
        self._raise_for_status(response)
        return cast("dict[str, Any]", response.json())

    def is_assignment_released(self, course_id: str, assignment_id: int) -> bool:
        response = self.session.get(
            self._api_url(f"/courses/{course_id}/assignments/{assignment_id}")
        )
        self._raise_for_status(response)
        return _published_item_is_released(cast("dict[str, Any]", response.json()))

    def create_rubric(self, course_id: str, form: dict[str, Any]) -> None:
        response = self.session.post(
            self._api_url(f"/courses/{course_id}/rubrics"),
            data=form,
        )
        self._raise_for_status(response)


class QuizCanvasClient(CanvasApiClient):
    def create_assignment_group(self, course_id: str, name: str) -> dict[str, Any]:
        response = self.session.post(
            self._api_url(f"/courses/{course_id}/assignment_groups"),
            data={"name": name},
        )
        self._raise_for_status(response)
        return cast("dict[str, Any]", response.json())

    def create_quiz(self, course_id: str, form: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            self._api_url(f"/courses/{course_id}/quizzes"),
            data=form,
        )
        self._raise_for_status(response)
        return cast("dict[str, Any]", response.json())

    def update_quiz(self, course_id: str, quiz_id: int, form: dict[str, Any]) -> dict[str, Any]:
        response = self.session.put(
            self._api_url(f"/courses/{course_id}/quizzes/{quiz_id}"),
            data=form,
        )
        self._raise_for_status(response)
        return cast("dict[str, Any]", response.json())

    def quiz_has_submissions(self, course_id: str, quiz_id: int) -> bool:
        response = self.session.get(
            self._api_url(f"/courses/{course_id}/quizzes/{quiz_id}/submissions"),
            params={"per_page": 100},
        )
        self._raise_for_status(response)
        data = response.json()
        submissions = data.get("quiz_submissions", []) if isinstance(data, dict) else []
        if not isinstance(submissions, list):
            return False
        for submission in submissions:
            if isinstance(submission, dict) and submission.get("workflow_state") != "preview":
                return True
        return False

    def is_quiz_released(self, course_id: str, quiz_id: int) -> bool:
        response = self.session.get(self._api_url(f"/courses/{course_id}/quizzes/{quiz_id}"))
        self._raise_for_status(response)
        return _published_item_is_released(cast("dict[str, Any]", response.json()))

    def list_quiz_questions(self, course_id: str, quiz_id: int) -> list[dict[str, Any]]:
        return self.get_paginated(
            f"/courses/{course_id}/quizzes/{quiz_id}/questions",
            params={"per_page": 100},
        )

    def create_quiz_question(
        self,
        course_id: str,
        quiz_id: int,
        question: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.session.post(
            self._api_url(f"/courses/{course_id}/quizzes/{quiz_id}/questions"),
            json={"question": question},
            headers={"Content-Type": "application/json"},
        )
        self._raise_for_status(response)
        return cast("dict[str, Any]", response.json())

    def delete_quiz_question(self, course_id: str, quiz_id: int, question_id: int) -> None:
        response = self.session.delete(
            self._api_url(f"/courses/{course_id}/quizzes/{quiz_id}/questions/{question_id}")
        )
        self._raise_for_status(response)


__all__ = ["AssignmentCanvasClient", "QuizCanvasClient"]
