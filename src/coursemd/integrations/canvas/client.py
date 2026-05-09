"""Canvas API client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Self, cast

import requests  # type: ignore[import-untyped]

from coursemd.integrations.canvas.config import DEFAULT_CANVAS_BASE_URL


@dataclass
class CanvasApiClient:
    """Common HTTP helpers shared by Canvas sync commands."""

    base_url: str
    token: str
    dry_run: bool = False
    _session: requests.Session | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def __enter__(self) -> Self:
        self._open_session()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def _open_session(self) -> requests.Session:
        if self._session is None:
            session = requests.Session()
            session.headers.update({"Authorization": f"Bearer {self.token}"})
            self._session = session
        return self._session

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            raise RuntimeError("CanvasApiClient must be used inside a 'with' block.")
        return self._session

    def _api_url(self, path: str) -> str:
        return f"{self.base_url}/api/v1/{path.lstrip('/')}"

    def _raise_for_status(self, response: requests.Response) -> None:
        if not response.ok:
            raise RuntimeError(
                f"Canvas API error ({response.status_code}) "
                f"{response.request.method} {response.url}\n{response.text}"
            )

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(self._api_url(path), params=params)
        self._raise_for_status(response)
        return cast("dict[str, Any]", response.json())

    def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        url: str | None = self._api_url(path)
        results: list[dict[str, Any]] = []
        while url:
            response = self.session.get(url, params=params)
            self._raise_for_status(response)
            results.extend(response.json())
            url = response.links.get("next", {}).get("url")
            params = None
        return results


__all__ = ["CanvasApiClient", "DEFAULT_CANVAS_BASE_URL"]
