from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

class ApiClientError(RuntimeError):
    pass

def _normalise_params(params: dict[str, Any] | None) -> dict[str, Any]:
    clean_params: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        clean_params[key] = value
    return clean_params

@dataclass(frozen=True)
class HDBApiClient:
    base_url: str
    timeout: int = 30

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(url, params=_normalise_params(params), timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ApiClientError(f"Could not reach API endpoint {url}: {exc}") from exc
        return response.json()

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ApiClientError(f"Could not reach API endpoint {url}: {exc}") from exc
        return response.json()
