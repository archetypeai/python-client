from __future__ import annotations

import os

import pytest

from archetypeai import ArchetypeAI


@pytest.fixture
def client() -> ArchetypeAI:
    """Attempts to initialize a client, if it fails it skips the tests."""
    api_key = os.getenv("ATAI_API_KEY", None)
    api_endpoint = os.getenv("ATAI_API_ENDPOINT", None)

    if api_key is None or api_endpoint is None:
        pytest.skip("Client is not initialized!")

    client = ArchetypeAI(api_key, api_endpoint=api_endpoint, request_timeout_sec=30)

    return client


@pytest.fixture
def uploaded_files(client: ArchetypeAI) -> list[str]:
    """Tracks uploaded file IDs and deletes them after the test."""
    file_ids: list[str] = []
    yield file_ids
    for file_id in file_ids:
        try:
            client.files.local.delete(file_id)
        except Exception as exc:
            # Best-effort cleanup: ignore deletion failures but log for debugging.
            print(f"Warning: failed to delete uploaded file {file_id!r}: {exc}")
