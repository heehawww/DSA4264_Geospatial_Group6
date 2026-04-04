from __future__ import annotations

from .data import DataStore, store


def get_store() -> DataStore:
    return store
