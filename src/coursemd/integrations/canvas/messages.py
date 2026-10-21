"""Templated Canvas conversation messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

import yaml
from jinja2 import Environment, StrictUndefined, TemplateError

from coursemd.core.exceptions import CoursemdValidationError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

MessageMode = Literal["group", "individual"]
MESSAGE_MODES: tuple[MessageMode, ...] = ("group", "individual")
RESERVED_ENTRY_KEYS = frozenset({"key", "to", "recipients"})


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CoursemdValidationError(f"Invalid YAML: {exc}", source_path=path) from exc


@dataclass(frozen=True)
class MessageTemplate:
    subject: str
    body: str
    source_file: Path
    mode: MessageMode = "group"
    defaults: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> MessageTemplate:
        raw = _load_yaml(path)
        if not isinstance(raw, dict):
            raise CoursemdValidationError("Message template must be a mapping.", source_path=path)
        subject = raw.get("subject")
        body = raw.get("body")
        if not isinstance(subject, str) or not subject.strip():
            raise CoursemdValidationError(
                "Message template requires a non-empty 'subject'.", source_path=path
            )
        if not isinstance(body, str) or not body.strip():
            raise CoursemdValidationError(
                "Message template requires a non-empty 'body'.", source_path=path
            )
        mode = raw.get("mode", "group")
        if mode not in MESSAGE_MODES:
            raise CoursemdValidationError(
                f"Message template 'mode' must be one of {', '.join(MESSAGE_MODES)}.",
                source_path=path,
            )
        defaults = raw.get("defaults") or {}
        if not isinstance(defaults, dict):
            raise CoursemdValidationError(
                "Message template 'defaults' must be a mapping.", source_path=path
            )
        unknown = sorted(set(raw) - {"subject", "body", "mode", "defaults"})
        if unknown:
            raise CoursemdValidationError(
                f"Unknown message template field(s): {', '.join(unknown)}", source_path=path
            )
        return cls(subject=subject, body=body, source_file=path, mode=mode, defaults=defaults)


@dataclass(frozen=True)
class MessageEntry:
    key: str
    users: tuple[str, ...]
    groups: tuple[str, ...]
    variables: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: Any, *, index: int) -> MessageEntry:
        if not isinstance(raw, dict):
            raise CoursemdValidationError(f"Message {index} must be a mapping.")
        users, groups = _parse_recipients(raw.get("to"), index=index)
        default_key = ",".join([*users, *(f"group:{group}" for group in groups)])
        key = raw.get("key", default_key)
        if not isinstance(key, str) or not key:
            raise CoursemdValidationError(f"Message {index} has an invalid 'key'.")
        variables = {name: value for name, value in raw.items() if name not in {"key", "to"}}
        if "recipients" in variables:
            raise CoursemdValidationError(
                f"Message {key!r} must not define reserved variable 'recipients'."
            )
        return cls(key=key, users=users, groups=groups, variables=variables)


def _parse_recipients(raw: Any, *, index: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    items = raw if isinstance(raw, list) else [raw]
    users: list[str] = []
    groups: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            users.append(item.strip())
        elif isinstance(item, dict) and set(item) == {"group"} and isinstance(item["group"], str):
            groups.append(item["group"])
        else:
            raise CoursemdValidationError(
                f"Message {index} has an invalid 'to' entry {item!r}; "
                "expected a user identifier or {group: <name>}."
            )
    if not users and not groups:
        raise CoursemdValidationError(f"Message {index} requires at least one 'to' recipient.")
    return tuple(users), tuple(groups)


@dataclass(frozen=True)
class MessageBatch:
    source_file: Path
    template_file: Path | None
    entries: list[MessageEntry]

    @property
    def ledger_file(self) -> Path:
        return self.source_file.with_name(f"{self.source_file.stem}.sent.yml")

    @classmethod
    def load(cls, path: Path) -> MessageBatch:
        raw = _load_yaml(path)
        if not isinstance(raw, dict):
            raise CoursemdValidationError(
                "Message data file must be a mapping with a 'messages' list.", source_path=path
            )
        unknown = sorted(set(raw) - {"template", "messages"})
        if unknown:
            raise CoursemdValidationError(
                f"Unknown message data field(s): {', '.join(unknown)}", source_path=path
            )
        template = raw.get("template")
        if template is not None and not isinstance(template, str):
            raise CoursemdValidationError("'template' must be a path.", source_path=path)
        raw_messages = raw.get("messages")
        if not isinstance(raw_messages, list) or not raw_messages:
            raise CoursemdValidationError(
                "Message data file requires a non-empty 'messages' list.", source_path=path
            )
        try:
            entries = [
                MessageEntry.from_dict(item, index=index) for index, item in enumerate(raw_messages)
            ]
        except CoursemdValidationError as exc:
            raise CoursemdValidationError(exc.message, source_path=path) from exc
        seen: set[str] = set()
        for entry in entries:
            if entry.key in seen:
                raise CoursemdValidationError(
                    f"Duplicate message key {entry.key!r}.", source_path=path
                )
            seen.add(entry.key)
        template_file = (path.parent / template).resolve() if template else None
        return cls(source_file=path, template_file=template_file, entries=entries)


@dataclass(frozen=True)
class CanvasRecipient:
    id: int | None
    name: str
    short_name: str
    login_id: str | None = None

    @classmethod
    def from_canvas(cls, user: dict[str, Any]) -> CanvasRecipient:
        name = str(user.get("name") or user.get("id"))
        return cls(
            id=int(user["id"]),
            name=name,
            short_name=str(user.get("short_name") or name),
            login_id=user.get("login_id"),
        )

    @classmethod
    def placeholder(cls, label: str) -> CanvasRecipient:
        return cls(id=None, name=label, short_name=label, login_id=None)

    def as_template_value(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "login_id": self.login_id,
        }


@dataclass(frozen=True)
class RenderedMessage:
    key: str
    subject: str
    body: str
    recipients: tuple[CanvasRecipient, ...]
    mode: MessageMode


def render_message(
    template: MessageTemplate,
    entry: MessageEntry,
    recipients: Sequence[CanvasRecipient],
) -> RenderedMessage:
    # Canvas conversation bodies are plain text, so HTML escaping would only corrupt them.
    env = Environment(undefined=StrictUndefined, autoescape=False)  # noqa: S701
    context = {
        **template.defaults,
        **entry.variables,
        "recipients": [recipient.as_template_value() for recipient in recipients],
    }
    try:
        subject = env.from_string(template.subject).render(context)
        body = env.from_string(template.body).render(context)
    except TemplateError as exc:
        raise CoursemdValidationError(
            f"Failed to render message {entry.key!r}: {exc}",
            source_path=template.source_file,
        ) from exc
    subject = " ".join(subject.split())
    if not subject:
        raise CoursemdValidationError(
            f"Message {entry.key!r} rendered an empty subject.",
            source_path=template.source_file,
        )
    return RenderedMessage(
        key=entry.key,
        subject=subject,
        body=body.strip() + "\n",
        recipients=tuple(recipients),
        mode=template.mode,
    )


class MessageDirectory(Protocol):
    def list_course_users(self, course_id: str) -> list[dict[str, Any]]: ...

    def list_course_groups(self, course_id: str) -> list[dict[str, Any]]: ...

    def list_group_users(self, group_id: int) -> list[dict[str, Any]]: ...


def _identifier_matches(user: dict[str, Any], identifier: str) -> bool:
    wanted = identifier.casefold()
    candidates = [
        str(user[name]).casefold()
        for name in ("login_id", "sis_user_id", "email")
        if user.get(name)
    ]
    if wanted in candidates:
        return True
    if "@" in wanted:
        return False
    return any(candidate.split("@", 1)[0] == wanted for candidate in candidates)


@dataclass
class RecipientResolver:
    """Resolves message recipients against a Canvas course roster and its groups."""

    directory: MessageDirectory
    course_id: str
    _users: list[dict[str, Any]] | None = field(init=False, default=None)
    _groups: list[dict[str, Any]] | None = field(init=False, default=None)
    _group_members: dict[int, list[dict[str, Any]]] = field(init=False, default_factory=dict)

    def _course_users(self) -> list[dict[str, Any]]:
        if self._users is None:
            self._users = self.directory.list_course_users(self.course_id)
        return self._users

    def _course_groups(self) -> list[dict[str, Any]]:
        if self._groups is None:
            self._groups = self.directory.list_course_groups(self.course_id)
        return self._groups

    def user(self, identifier: str) -> dict[str, Any]:
        matches = {
            int(user["id"]): user
            for user in self._course_users()
            if _identifier_matches(user, identifier)
        }
        if not matches:
            raise CoursemdValidationError(f"No Canvas user in the course matches {identifier!r}.")
        if len(matches) > 1:
            raise CoursemdValidationError(
                f"{identifier!r} matches multiple Canvas users: "
                + ", ".join(str(user.get("name")) for user in matches.values())
            )
        return next(iter(matches.values()))

    def group_users(self, name: str) -> list[dict[str, Any]]:
        matches = [group for group in self._course_groups() if group.get("name") == name]
        if not matches:
            raise CoursemdValidationError(f"No Canvas group in the course is named {name!r}.")
        if len(matches) > 1:
            raise CoursemdValidationError(f"Multiple Canvas groups are named {name!r}.")
        group_id = int(matches[0]["id"])
        if group_id not in self._group_members:
            self._group_members[group_id] = self.directory.list_group_users(group_id)
        members = self._group_members[group_id]
        if not members:
            raise CoursemdValidationError(f"Canvas group {name!r} has no members.")
        return members

    def resolve(self, entry: MessageEntry) -> tuple[CanvasRecipient, ...]:
        users = [self.user(identifier) for identifier in entry.users]
        for group in entry.groups:
            users.extend(self.group_users(group))
        unique = {int(user["id"]): user for user in users}
        return tuple(CanvasRecipient.from_canvas(user) for user in unique.values())


def placeholder_recipients(entry: MessageEntry) -> tuple[CanvasRecipient, ...]:
    """Stand-in recipients used to render messages without contacting Canvas."""

    return (
        *(CanvasRecipient.placeholder(identifier) for identifier in entry.users),
        *(CanvasRecipient.placeholder(f"<members of {group}>") for group in entry.groups),
    )


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = _load_yaml(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CoursemdValidationError("Message ledger must be a mapping.", source_path=path)
    return raw


def record_sent_message(
    path: Path,
    message: RenderedMessage,
    conversation_ids: Sequence[int],
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """Append a sent message to the ledger so later runs skip it."""

    ledger = load_ledger(path)
    ledger[message.key] = {
        "sent_at": now().isoformat(timespec="seconds"),
        "subject": message.subject,
        "recipients": [
            recipient.login_id or recipient.name for recipient in message.recipients
        ],
        "conversation_ids": list(conversation_ids),
    }
    path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")


def conversation_form(message: RenderedMessage, *, course_id: str) -> dict[str, Any]:
    recipient_ids = [str(recipient.id) for recipient in message.recipients]
    if any(recipient.id is None for recipient in message.recipients):
        raise CoursemdValidationError(f"Message {message.key!r} has unresolved recipients.")
    return {
        "recipients[]": recipient_ids,
        "subject": message.subject,
        "body": message.body,
        "group_conversation": "true" if message.mode == "group" else "false",
        "force_new": "true",
        "context_code": f"course_{course_id}",
    }


__all__ = (
    "CanvasRecipient",
    "MessageBatch",
    "MessageEntry",
    "MessageTemplate",
    "RecipientResolver",
    "RenderedMessage",
    "conversation_form",
    "load_ledger",
    "placeholder_recipients",
    "record_sent_message",
    "render_message",
)
