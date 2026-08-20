# Shared helpers for the agent examples: safe handling of API responses,
# bundle discovery, and input file upload.
import logging
import os

from archetypeai import ApiError, ArchetypeAI, pformat


def require(response: dict, key: str):
    """Returns a required field of an API response, failing with the full response if it is missing."""
    value = response.get(key)
    assert value, f"Malformed API response, missing '{key}': {pformat(response)}"
    return value


def pick_bundle(client: ArchetypeAI, name: str) -> dict:
    """Picks the newest bundle whose name matches (case-insensitive substring)."""
    bundles = client.agents.bundles.list(query=name).get("data")
    assert bundles, f"No bundle matching '{name}' available to your org"
    return bundles[0]


def get_or_upload_file(client: ArchetypeAI, filename: str) -> str:
    """Uses the file if it is already on the platform, otherwise uploads it."""
    file_id = os.path.basename(filename)
    try:
        client.files.get_metadata(file_id=file_id)
        logging.info(f"Input file already on the platform: {file_id}")
    except ApiError:
        file_id = require(client.files.local.upload(filename), "file_id")
        logging.info(f"Uploaded input file: {file_id}")
    return file_id
