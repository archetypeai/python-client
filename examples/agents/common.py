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
    """Picks the bundle whose name matches EXACTLY, preferring canonical ones.

    `query` is a case-insensitive substring search over name and id, and results
    come back newest-first — so a PREFIX of a quick-start name matches the
    Embeddings variant too, and that variant sorts first. Taking bundles[0]
    therefore runs the wrong bundle: on the OSM sample slice that is a 314 MB
    embeddings output where a 221 KB prediction file was expected.

        query 'OSM Quick Start'                   -> 2 rows, Embeddings first
        query 'OSM Quick Start (Volve Six State)' -> 1 row

    Canonical (platform-published) bundles win over a same-named org bundle.
    """
    bundles = client.agents.bundles.list(query=name).get("data") or []
    exact = [b for b in bundles if b.get("name") == name]
    assert exact, (
        f"No bundle named exactly '{name}' available to your org "
        f"(query returned {[b.get('name') for b in bundles]})")
    for bundle in exact:
        if bundle.get("is_canonical"):
            return bundle
    return exact[0]


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
