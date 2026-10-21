from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Any, Self

import pytest
import yaml
from typer.testing import CliRunner

import coursemd.integrations.canvas.cli
from coursemd import cli
from coursemd.core.exceptions import CoursemdValidationError
from coursemd.integrations.canvas.messages import (
    MessageBatch,
    MessageEntry,
    MessageTemplate,
    RecipientResolver,
    conversation_form,
    placeholder_recipients,
    render_message,
)

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

USERS = [
    {"id": 1, "name": "Alice Adams", "short_name": "Alice", "login_id": "alice@andrew.cmu.edu"},
    {"id": 2, "name": "Bob Brown", "short_name": "Bob", "login_id": "bob", "email": "b@x.edu"},
    {"id": 3, "name": "Carol Chen", "short_name": "Carol", "sis_user_id": "carol"},
    {"id": 4, "name": "Dup One", "short_name": "Dup", "login_id": "dup@andrew.cmu.edu"},
    {"id": 5, "name": "Dup Two", "short_name": "Dup", "email": "dup@example.com"},
]
GROUPS = [{"id": 10, "name": "Team 1"}, {"id": 11, "name": "Empty"}]
GROUP_USERS = {10: [USERS[0], USERS[1]], 11: []}


class FakeDirectory:
    def __init__(self) -> None:
        self.user_calls = 0

    def list_course_users(self, course_id: str) -> list[dict[str, Any]]:  # noqa: ARG002
        self.user_calls += 1
        return USERS

    def list_course_groups(self, course_id: str) -> list[dict[str, Any]]:  # noqa: ARG002
        return GROUPS

    def list_group_users(self, group_id: int) -> list[dict[str, Any]]:
        return GROUP_USERS[group_id]


def _write(path: Path, contents: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(contents), encoding="utf-8")
    return path


def _template(tmp_path: Path, **overrides: Any) -> MessageTemplate:
    raw = {
        "subject": "Feedback for {{ team }}",
        "body": "Hi {{ recipients | map(attribute='short_name') | join(', ') }}: {{ score }}",
        **overrides,
    }
    path = tmp_path / "template.yml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return MessageTemplate.load(path)


def test_template_rejects_unknown_mode(tmp_path: Path) -> None:
    with pytest.raises(CoursemdValidationError, match="'mode' must be one of"):
        _template(tmp_path, mode="broadcast")


def test_entry_parses_users_groups_and_default_key() -> None:
    entry = MessageEntry.from_dict({"to": ["alice", {"group": "Team 1"}], "score": 3}, index=0)

    assert entry.users == ("alice",)
    assert entry.groups == ("Team 1",)
    assert entry.key == "alice,group:Team 1"
    assert entry.variables == {"score": 3}


def test_entry_rejects_reserved_recipients_variable() -> None:
    with pytest.raises(CoursemdValidationError, match="reserved variable 'recipients'"):
        MessageEntry.from_dict({"to": "alice", "recipients": []}, index=0)


def test_batch_rejects_duplicate_keys_and_resolves_template_relative_to_data(
    tmp_path: Path,
) -> None:
    data = _write(
        tmp_path / "msgs" / "data.yml",
        """
        template: ../templates/t.yml
        messages:
          - to: alice
          - to: bob
        """,
    )
    batch = MessageBatch.load(data)
    assert batch.template_file == (tmp_path / "templates" / "t.yml").resolve()
    assert batch.ledger_file == tmp_path / "msgs" / "data.sent.yml"

    _write(data, "messages:\n  - to: alice\n  - to: bob\n    key: alice\n")
    with pytest.raises(CoursemdValidationError, match="Duplicate message key 'alice'"):
        MessageBatch.load(data)


def test_render_applies_defaults_and_entry_overrides(tmp_path: Path) -> None:
    template = _template(tmp_path, defaults={"score": 0, "team": "?"})
    entry = MessageEntry.from_dict({"to": "alice", "team": "Team 1"}, index=0)

    message = render_message(template, entry, placeholder_recipients(entry))

    assert message.subject == "Feedback for Team 1"
    assert message.body == "Hi alice: 0\n"


def test_render_fails_on_missing_variable(tmp_path: Path) -> None:
    template = _template(tmp_path)
    entry = MessageEntry.from_dict({"to": "alice", "team": "Team 1"}, index=0)

    with pytest.raises(CoursemdValidationError, match="'score' is undefined"):
        render_message(template, entry, placeholder_recipients(entry))


def test_resolver_matches_identifiers_and_expands_groups() -> None:
    directory = FakeDirectory()
    resolver = RecipientResolver(directory=directory, course_id="1")
    entry = MessageEntry.from_dict(
        {"to": ["alice", "B@X.EDU", "carol", {"group": "Team 1"}]}, index=0
    )

    recipients = resolver.resolve(entry)

    assert [recipient.id for recipient in recipients] == [1, 2, 3]
    assert recipients[0].short_name == "Alice"
    resolver.resolve(entry)
    assert directory.user_calls == 1


@pytest.mark.parametrize(
    ("to", "error"),
    [
        ("nobody", "No Canvas user in the course matches 'nobody'"),
        ("dup", "matches multiple Canvas users"),
        ({"group": "Team 9"}, "No Canvas group in the course is named 'Team 9'"),
        ({"group": "Empty"}, "has no members"),
    ],
)
def test_resolver_rejects_unknown_or_ambiguous_recipients(to: Any, error: str) -> None:
    resolver = RecipientResolver(directory=FakeDirectory(), course_id="1")
    entry = MessageEntry.from_dict({"to": to}, index=0)

    with pytest.raises(CoursemdValidationError, match=error):
        resolver.resolve(entry)


@pytest.mark.parametrize(
    ("mode", "group_conversation"), [("group", "true"), ("individual", "false")]
)
def test_conversation_form_uses_mode(tmp_path: Path, mode: str, group_conversation: str) -> None:
    template = _template(tmp_path, mode=mode)
    entry = MessageEntry.from_dict({"to": "alice", "team": "T", "score": 1}, index=0)
    resolver = RecipientResolver(directory=FakeDirectory(), course_id="1")
    message = render_message(template, entry, resolver.resolve(entry))

    form = conversation_form(message, course_id="99")

    assert form["recipients[]"] == ["1"]
    assert form["group_conversation"] == group_conversation
    assert form["force_new"] == "true"
    assert form["context_code"] == "course_99"


class FakeMessageClient(FakeDirectory):
    sent: list[dict[str, Any]]

    def __init__(self, **_: Any) -> None:
        super().__init__()
        type(self).sent = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def create_conversation(self, form: dict[str, Any]) -> list[dict[str, Any]]:
        type(self).sent.append(form)
        return [{"id": 100 + len(type(self).sent)}]


@pytest.fixture
def message_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write(
        tmp_path / ".coursemd.yml",
        """
        integrations:
          mkdocs:
            base_url: https://example.edu/course
            project_dir: website
          canvas:
            base_url: https://canvas.example.edu
            course_id: 12345
        """,
    )
    _write(
        tmp_path / "messages" / "hw3.yml",
        """
        subject: "HW3 for {{ team }}"
        body: |
          Hi {{ recipients | map(attribute="short_name") | join(", ") }},
          Score: {{ score }}
        """,
    )
    _write(
        tmp_path / "messages" / "hw3.data.yml",
        """
        template: hw3.yml
        messages:
          - key: team-1
            to: {group: Team 1}
            team: Team 1
            score: 87
          - to: carol
            team: Solo
            score: 92
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CANVAS_TOKEN", "token")
    monkeypatch.setattr(
        coursemd.integrations.canvas.cli, "MessageCanvasClient", FakeMessageClient
    )
    return tmp_path


def test_message_plan_only_renders_without_canvas(message_repo: Path) -> None:
    del message_repo
    result = runner.invoke(
        cli.app, ["canvas", "message", "messages/hw3.data.yml", "--plan-only"]
    )

    assert result.exit_code == 0, result.output
    assert "=== team-1 [group] ===" in result.stdout
    assert "Hi <members of Team 1>," in result.stdout
    assert "Subject: HW3 for Solo" in result.stdout
    assert "Rendered 2 message(s)" in result.stdout


def test_message_dry_run_resolves_but_does_not_send(message_repo: Path) -> None:
    del message_repo
    result = runner.invoke(cli.app, ["canvas", "message", "messages/hw3.data.yml", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "To: Alice Adams (alice@andrew.cmu.edu), Bob Brown (bob)" in result.stdout
    assert "Hi Alice, Bob," in result.stdout
    assert "[dry-run] Would send 2 message(s) to 3 recipient(s)." in result.stdout
    assert FakeMessageClient.sent == []


def test_message_send_requires_confirmation(message_repo: Path) -> None:
    result = runner.invoke(
        cli.app, ["canvas", "message", "messages/hw3.data.yml"], input="n\n"
    )

    assert result.exit_code == 1
    assert FakeMessageClient.sent == []
    assert not (message_repo / "messages" / "hw3.data.sent.yml").exists()


def test_message_send_records_ledger_and_skips_on_rerun(message_repo: Path) -> None:
    ledger_path = message_repo / "messages" / "hw3.data.sent.yml"

    result = runner.invoke(
        cli.app, ["canvas", "message", "messages/hw3.data.yml", "--only", "team-1", "--yes"]
    )

    assert result.exit_code == 0, result.output
    assert [form["recipients[]"] for form in FakeMessageClient.sent] == [["1", "2"]]
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    assert list(ledger) == ["team-1"]
    assert ledger["team-1"]["conversation_ids"] == [101]
    assert ledger["team-1"]["recipients"] == ["alice@andrew.cmu.edu", "bob"]

    result = runner.invoke(cli.app, ["canvas", "message", "messages/hw3.data.yml", "--yes"])

    assert result.exit_code == 0, result.output
    assert "Skipping 'team-1': already sent" in result.stdout
    assert [form["subject"] for form in FakeMessageClient.sent] == ["HW3 for Solo"]
    assert list(yaml.safe_load(ledger_path.read_text(encoding="utf-8"))) == ["team-1", "carol"]

    result = runner.invoke(
        cli.app,
        ["canvas", "message", "messages/hw3.data.yml", "--only", "team-1", "--resend", "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert len(FakeMessageClient.sent) == 1


def test_message_rejects_unknown_only_key(message_repo: Path) -> None:
    del message_repo
    result = runner.invoke(
        cli.app, ["canvas", "message", "messages/hw3.data.yml", "--only", "nope", "--plan-only"]
    )

    assert result.exit_code == 1
    assert "Unknown message key(s): nope" in str(result.exception)
