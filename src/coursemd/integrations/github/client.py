"""GitHub API clients."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_ACCEPT_HEADER = "Accept: application/vnd.github+json"
_API_VERSION_HEADER = "X-GitHub-Api-Version: 2022-11-28"


class GitHubClientError(RuntimeError):
    """Raised when a GitHub adapter operation fails."""


class GitHubClient(Protocol):
    """Minimal GitHub operations needed by organization setup."""

    def ensure_available(self) -> None:
        """Verify the client can be used."""

    def ensure_authenticated(self) -> None:
        """Verify the client is authenticated."""

    def get_team_id(self, *, organization: str, team_slug: str) -> int:
        """Resolve a team slug to a numeric team ID."""

    def get_default_repository_permission(self, *, organization: str) -> str:
        """Read the organization's default repository permission."""

    def set_default_repository_permission(self, *, organization: str, permission: str) -> None:
        """Update the organization's default repository permission."""

    def find_ruleset_id(self, *, organization: str, ruleset_name: str) -> int | None:
        """Find an organization ruleset by name."""

    def create_ruleset(self, *, organization: str, payload: dict[str, Any]) -> int | None:
        """Create an organization ruleset and return its ID when available."""

    def update_ruleset(
        self,
        *,
        organization: str,
        ruleset_id: int,
        payload: dict[str, Any],
    ) -> int | None:
        """Update an organization ruleset and return its ID when available."""


def run_command(
    args: Sequence[str],
    *,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and capture text output."""

    return subprocess.run(
        list(args),
        check=False,
        capture_output=True,
        input=input_text,
        text=True,
    )


class GhCliGitHubClient:
    """GitHub API client backed by the GitHub CLI."""

    def __init__(
        self,
        *,
        command_runner: (
            Callable[..., subprocess.CompletedProcess[str]] | None
        ) = None,
    ) -> None:
        self._command_runner = command_runner or run_command

    def ensure_available(self) -> None:
        if shutil.which("gh") is None:
            raise GitHubClientError(
                "GitHub CLI (gh) is not installed. Install it from: https://cli.github.com/"
            )

    def ensure_authenticated(self) -> None:
        result = self._run(["gh", "auth", "status"])
        if result.returncode != 0:
            raise GitHubClientError("Not authenticated with GitHub CLI. Run: gh auth login")

    def get_team_id(self, *, organization: str, team_slug: str) -> int:
        payload = self._api_object(
            f"/orgs/{organization}/teams/{team_slug}",
            error_message=(
                f"Could not find team '{team_slug}' in org '{organization}'. "
                "Make sure the team exists and your token has the required permissions."
            ),
        )
        team_id = payload.get("id")
        if not isinstance(team_id, int):
            raise GitHubClientError(
                f"Could not resolve a numeric team ID for '{team_slug}' in org '{organization}'."
            )
        return team_id

    def get_default_repository_permission(self, *, organization: str) -> str:
        payload = self._api_object(
            f"/orgs/{organization}",
            error_message=f"Could not read organization settings for '{organization}'.",
        )
        current_permission = payload.get("default_repository_permission")
        return current_permission if isinstance(current_permission, str) else "unknown"

    def set_default_repository_permission(self, *, organization: str, permission: str) -> None:
        self._api_object(
            f"/orgs/{organization}",
            method="PATCH",
            fields={"default_repository_permission": permission},
            error_message=f"Could not update organization settings for '{organization}'.",
        )

    def find_ruleset_id(self, *, organization: str, ruleset_name: str) -> int | None:
        rulesets = self._api_list(
            f"/orgs/{organization}/rulesets",
            error_message=f"Could not list organization rulesets for '{organization}'.",
        )
        for ruleset in rulesets:
            if ruleset.get("name") == ruleset_name and isinstance(ruleset.get("id"), int):
                return int(ruleset["id"])
        return None

    def create_ruleset(self, *, organization: str, payload: dict[str, Any]) -> int | None:
        response_payload = self._api_object(
            f"/orgs/{organization}/rulesets",
            method="POST",
            input_json=payload,
            error_message=f"Could not create ruleset '{payload.get('name')}' for '{organization}'.",
        )
        return self._optional_int_id(response_payload)

    def update_ruleset(
        self,
        *,
        organization: str,
        ruleset_id: int,
        payload: dict[str, Any],
    ) -> int | None:
        response_payload = self._api_object(
            f"/orgs/{organization}/rulesets/{ruleset_id}",
            method="PUT",
            input_json=payload,
            error_message=f"Could not update ruleset '{payload.get('name')}' for '{organization}'.",
        )
        return self._optional_int_id(response_payload)

    def _run(
        self,
        args: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return self._command_runner(args, input_text=input_text)  # type: ignore[call-arg]
        except TypeError:
            return self._command_runner(args)  # type: ignore[misc]

    def _gh_api(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        fields: dict[str, str] | None = None,
        input_json: dict[str, Any] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        args = [
            "gh",
            "api",
            "-H",
            _ACCEPT_HEADER,
            "-H",
            _API_VERSION_HEADER,
        ]
        if method != "GET":
            args.extend(["--method", method])
        if fields:
            for key, value in fields.items():
                args.extend(["-f", f"{key}={value}"])
        input_text: str | None = None
        if input_json is not None:
            args.extend(["--input", "-"])
            input_text = json.dumps(input_json)
        args.append(endpoint)
        return self._run(args, input_text=input_text)

    def _api_object(
        self,
        endpoint: str,
        *,
        error_message: str,
        method: str = "GET",
        fields: dict[str, str] | None = None,
        input_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self._gh_api(
            endpoint,
            method=method,
            fields=fields,
            input_json=input_json,
        )
        return decode_json_response(result, error_message=error_message)

    def _api_list(self, endpoint: str, *, error_message: str) -> list[dict[str, Any]]:
        return decode_json_list_response(
            self._gh_api(endpoint),
            error_message=error_message,
        )

    @staticmethod
    def _optional_int_id(payload: dict[str, Any]) -> int | None:
        value = payload.get("id")
        return value if isinstance(value, int) else None


def decode_json_response(
    result: subprocess.CompletedProcess[str],
    *,
    error_message: str,
) -> dict[str, Any]:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GitHubClientError(f"{error_message}\n{detail}".rstrip())
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise GitHubClientError(f"{error_message}\nInvalid JSON response from gh api.") from exc
    if not isinstance(payload, dict):
        raise GitHubClientError(f"{error_message}\nExpected a JSON object from gh api.")
    return payload


def decode_json_list_response(
    result: subprocess.CompletedProcess[str],
    *,
    error_message: str,
) -> list[dict[str, Any]]:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GitHubClientError(f"{error_message}\n{detail}".rstrip())
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise GitHubClientError(f"{error_message}\nInvalid JSON response from gh api.") from exc
    if not isinstance(payload, list):
        raise GitHubClientError(f"{error_message}\nExpected a JSON array from gh api.")
    return [item for item in payload if isinstance(item, dict)]
