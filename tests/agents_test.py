from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from archetypeai import ArchetypeAI, pformat
from archetypeai._agents import _drop_missing

EXAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "example_data"
OSM_SENSOR_LOG = EXAMPLE_DATA_DIR / "osm_quick_start_drilling_log.csv"

# Generous ceiling for the agent run; OSM usually finishes the sample sensor
# log in a few minutes.
MAX_AGENT_RUN_TIME_SEC = 900.0


def test_drop_missing_lowercases_booleans():
    """Query params must carry lowercase `true`/`false`.

    The API's query-string deserialiser rejects Python's "True"/"False" with
    400 "provided string was not `true` or `false`", and the client surfaces
    that as an empty ApiError, so the cause is invisible. Verified against
    prod: ?yaml=True -> 400, ?yaml=true -> 200.

    Runs offline; no client fixture needed.
    """
    assert _drop_missing({"yaml": True}) == {"yaml": "true"}
    assert _drop_missing({"yaml": False}) == {"yaml": "false"}
    # None still means "unset", and non-booleans pass through untouched
    assert _drop_missing({"yaml": None}) == {}
    assert _drop_missing({"limit": 100, "after": "cur", "query": "OSM"}) == {
        "limit": 100, "after": "cur", "query": "OSM"}
    # ints must not be mangled into strings by the bool branch
    assert _drop_missing({"limit": 0}) == {"limit": 0}


def require(response: dict, key: str):
    """Returns a required field of an API response, failing with the full response if it is missing."""
    value = response.get(key)
    assert value, f"Malformed API response, missing '{key}': {pformat(response)}"
    return value


# Platform quick-start bundle names used by the OSM/RED/AD examples; bundle ids differ between envs.
OSM_BUNDLE_NAME = "OSM Quick Start (Volve Six State)"
RED_BUNDLE_NAME = "RED Quick Start (Pump Breakdown)"
AD_BUNDLE_NAME = "AD Quick Start (Bearing Breakdown)"
# Canonical blueprint keys used by the MGA/TVA examples; blueprint ids differ between envs.
MGA_BLUEPRINT_KEY = "mga"
TVA_BLUEPRINT_KEY = "tva"


def pick_bundle(client: ArchetypeAI, name: str) -> dict:
    """Picks the newest bundle whose name matches (case-insensitive substring)."""
    bundles = client.agents.bundles.list(query=name).get("data")
    assert bundles, f"No bundle matching '{name}' available to the org"
    return bundles[0]


def test_osm_bundle_visible(client: ArchetypeAI):
    bundle = pick_bundle(client, OSM_BUNDLE_NAME)
    require(bundle, "id")


def test_red_bundle_visible(client: ArchetypeAI):
    bundle = pick_bundle(client, RED_BUNDLE_NAME)
    require(bundle, "id")


def test_ad_bundle_visible(client: ArchetypeAI):
    bundle = pick_bundle(client, AD_BUNDLE_NAME)
    require(bundle, "id")


def test_mga_blueprint_visible(client: ArchetypeAI):
    blueprint = client.agents.blueprints.get(MGA_BLUEPRINT_KEY)
    assert blueprint.get("blueprint_key") == MGA_BLUEPRINT_KEY, pformat(blueprint)
    require(blueprint, "id")


def test_mga_bundle_create(client: ArchetypeAI):
    """Create a bundle from the MGA blueprint key, then fetch it by bundle_id."""
    blueprint_id = require(client.agents.blueprints.get(MGA_BLUEPRINT_KEY), "id")
    bundle_name = f"manual_generation_test_bundle_{uuid.uuid4().hex[:8]}"
    created = client.agents.bundles.create(blueprint=MGA_BLUEPRINT_KEY, name=bundle_name)
    bundle_id = require(created, "id")
    try:
        bundle = client.agents.bundles.get(bundle_id)
        assert bundle.get("id") == bundle_id, pformat(bundle)
        assert bundle.get("blueprint_id") == blueprint_id, pformat(bundle)
        assert bundle.get("status") == "ready", pformat(bundle)
    finally:
        client.agents.bundles.delete(bundle_id)


def test_tva_blueprint_visible(client: ArchetypeAI):
    blueprint = client.agents.blueprints.get(TVA_BLUEPRINT_KEY)
    assert blueprint.get("blueprint_key") == TVA_BLUEPRINT_KEY, pformat(blueprint)
    require(blueprint, "id")


def test_tva_bundle_create(client: ArchetypeAI):
    """Create a bundle from the TVA blueprint key, then fetch it by bundle_id."""
    blueprint_id = require(client.agents.blueprints.get(TVA_BLUEPRINT_KEY), "id")
    bundle_name = f"task_verification_test_bundle_{uuid.uuid4().hex[:8]}"
    created = client.agents.bundles.create(blueprint=TVA_BLUEPRINT_KEY, name=bundle_name)
    bundle_id = require(created, "id")
    try:
        bundle = client.agents.bundles.get(bundle_id)
        assert bundle.get("id") == bundle_id, pformat(bundle)
        assert bundle.get("blueprint_id") == blueprint_id, pformat(bundle)
        assert bundle.get("status") == "ready", pformat(bundle)
    finally:
        client.agents.bundles.delete(bundle_id)


def test_osm_example_end_to_end(client: ArchetypeAI, uploaded_files: list[str]):
    """OSM example flow: discover the bundle by name, upload sample log, run, read results."""
    bundle = pick_bundle(client, OSM_BUNDLE_NAME)
    bundle_id = require(bundle, "id")

    file_id = require(client.files.local.upload(OSM_SENSOR_LOG), "file_id")
    uploaded_files.append(file_id)

    agent = client.agents.bundles.run(bundle_id, source=[file_id])
    agent_id = require(agent, "id")

    agent = client.agents.instances.wait_until_done(agent_id, timeout_sec=MAX_AGENT_RUN_TIME_SEC)
    if agent.get("status") != "completed":
        events = client.agents.instances.get_events(agent_id)
        pytest.fail(f"Agent {agent_id} finished with status {agent.get('status')}: {pformat(events)}")

    results = client.agents.instances.get_results(agent_id)
    assert results.get("data"), f"Completed agent returned no results: {pformat(results)}"
