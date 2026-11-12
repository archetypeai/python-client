from __future__ import annotations

import csv
import gzip
import shutil
import uuid
from pathlib import Path

import pytest

from archetypeai import ArchetypeAI, pformat

EXAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "example_data"
OSM_SENSOR_LOG = EXAMPLE_DATA_DIR / "osm_quick_start_volve_f14_log.csv"
# Blueprints the OSM/RED/AD demo examples and the OD example run, and the sample log each one runs on.
OSM_DEMO_BLUEPRINT_KEY = "playground-osm-drilling"
DEMO_LOGS = {
    OSM_DEMO_BLUEPRINT_KEY: OSM_SENSOR_LOG,
    "playground-red": EXAMPLE_DATA_DIR / "red_quick_start_pump_log.csv",
    "playground-ad": EXAMPLE_DATA_DIR / "ad_quick_start_bearing_log.csv",
    "od": EXAMPLE_DATA_DIR / "od_metropt" / "metropt_compressor_2020-07.csv.gz",
}
# Values a demo copy needs in place of its blueprint's: `od` scores one-hour windows of the 10 s MetroPT log.
DEMO_OVERRIDES = {"od": {"values": {"window_size": 360, "step_size": 360}}}

# Generous ceiling for the agent run; OSM usually finishes the sample sensor
# log in a few minutes.
MAX_AGENT_RUN_TIME_SEC = 900.0
# Ceiling for building a package.
MAX_PACKAGE_BUILD_TIME_SEC = 300.0


def require(response: dict, key: str):
    """Returns a required field of an API response, failing with the full response if it is missing."""
    value = response.get(key)
    assert value, f"Malformed API response, missing '{key}': {pformat(response)}"
    return value


# Canonical blueprint keys used by the MGA/TVA examples; blueprint ids differ between envs.
MGA_BLUEPRINT_KEY = "mga"
TVA_BLUEPRINT_KEY = "tva"
# Rows of the OSM sensor log sent in one serving query.
ROWS_PER_QUERY = 200


def copy_into(client: ArchetypeAI, project_id: str, blueprint_key: str, overrides: dict | None = None) -> str:
    """Copies a platform blueprint into the test's project, where its package can be deployed; returns the copy's ID."""
    copy = client.agents.blueprints.copy(
        blueprint_key,
        project_id=project_id,
        blueprint_key=f"{blueprint_key}-test-{uuid.uuid4().hex[:8]}",
        overrides=overrides,
    )
    return require(copy, "id")


def build_package(client: ArchetypeAI, blueprint_id: str, name: str) -> str:
    """Builds a package of a blueprint, waits until it is ready, and returns its ID."""
    package_id = require(client.agents.packages.create(blueprint_id, name=name), "id")
    package = client.agents.packages.wait_until_ready(package_id, timeout_sec=MAX_PACKAGE_BUILD_TIME_SEC)
    assert package.get("status") == "ready", pformat(package)
    return package_id


def delete_run(client: ArchetypeAI, session_id: str | None, deployment_id: str | None, package_id: str) -> None:
    """Deletes a session, its deployment and its package, each of which blocks deleting the next."""
    if session_id:
        if client.agents.sessions.get(session_id).get("status") not in ("completed", "failed", "cancelled"):
            client.agents.sessions.cancel(session_id)
        client.agents.sessions.delete(session_id)
    if deployment_id:
        if client.agents.deployments.get(deployment_id).get("status") not in ("stopped", "failed"):
            client.agents.deployments.stop(deployment_id)
        client.agents.deployments.wait_until_ready(deployment_id, timeout_sec=300.0)
        client.agents.deployments.delete(deployment_id)
    client.agents.packages.delete(package_id)


@pytest.mark.parametrize("blueprint_key", [MGA_BLUEPRINT_KEY, TVA_BLUEPRINT_KEY, *DEMO_LOGS])
def test_canonical_blueprint_visible(client: ArchetypeAI, blueprint_key: str):
    blueprint = client.agents.blueprints.get(blueprint_key)
    assert blueprint.get("blueprint_key") == blueprint_key, pformat(blueprint)
    require(blueprint, "id")


@pytest.mark.parametrize("blueprint_key", [MGA_BLUEPRINT_KEY, TVA_BLUEPRINT_KEY])
def test_package_create_in_project(client: ArchetypeAI, project: str, blueprint_key: str):
    """Copy a canonical blueprint into a project, then build a named package of it in that project."""
    blueprint_id = copy_into(client, project, blueprint_key)
    package_name = f"{blueprint_key}_test_package_{uuid.uuid4().hex[:8]}"
    package_id = build_package(client, blueprint_id, package_name)
    try:
        package = client.agents.packages.get(package_id)
        assert package.get("name") == package_name, pformat(package)
        held = [blueprint.get("blueprint_id") for blueprint in package.get("blueprints", [])]
        assert held == [blueprint_id], pformat(package)
        listed = client.agents.packages.list(project_id=project).get("data", [])
        assert package_id in [item.get("id") for item in listed], pformat(listed)
    finally:
        client.agents.packages.delete(package_id)


@pytest.mark.parametrize("blueprint_key", sorted(DEMO_LOGS))
def test_demo_batch_session_end_to_end(
    client: ArchetypeAI, project: str, uploaded_files: list[str], tmp_path: Path, blueprint_key: str
):
    """Demo example flow: copy the demo blueprint, package, deploy as batch, run a session, read results."""
    blueprint_id = copy_into(client, project, blueprint_key, DEMO_OVERRIDES.get(blueprint_key))
    package_id = build_package(client, blueprint_id, f"{blueprint_key}_test_package_{uuid.uuid4().hex[:8]}")
    log = DEMO_LOGS[blueprint_key]
    if log.suffix == ".gz":
        # The platform reads plain CSV.
        unpacked = tmp_path / log.stem
        with gzip.open(log, "rb") as packed, unpacked.open("wb") as out:
            shutil.copyfileobj(packed, out)
        log = unpacked
    file_id = require(client.files.local.upload(log), "file_id")
    uploaded_files.append(file_id)

    deployment_id = session_id = None
    try:
        deployment_id = require(client.agents.deployments.create(package_id, kind="batch"), "id")
        deployment = client.agents.deployments.wait_until_ready(deployment_id, timeout_sec=300.0)
        assert deployment.get("status") == "ready", pformat(deployment)
        assert deployment.get("project_id") == project, pformat(deployment)

        session_id = require(client.agents.sessions.create(deployment_id, source=[file_id]), "id")
        listed = client.agents.sessions.list(deployment_id=deployment_id).get("data", [])
        assert session_id in [item.get("id") for item in listed], pformat(listed)

        session = client.agents.sessions.wait_until_done(session_id, timeout_sec=MAX_AGENT_RUN_TIME_SEC)
        if session.get("status") != "completed":
            events = client.agents.sessions.get_events(session_id)
            pytest.fail(f"Session {session_id} finished with status {session.get('status')}: {pformat(events)}")

        results = client.agents.sessions.get_results(session_id)
        assert results.get("data"), f"Completed session returned no results: {pformat(results)}"
    finally:
        delete_run(client, session_id, deployment_id, package_id)


def test_osm_serving_session_query(client: ArchetypeAI, project: str):
    """OSM serving flow: deploy the demo blueprint as serving, open a session, and query it."""
    blueprint_id = copy_into(client, project, OSM_DEMO_BLUEPRINT_KEY)
    package_id = build_package(client, blueprint_id, f"osm_serving_test_package_{uuid.uuid4().hex[:8]}")

    deployment_id = session_id = None
    try:
        deployment_id = require(client.agents.deployments.create(package_id, kind="serving"), "id")
        deployment = client.agents.deployments.wait_until_ready(deployment_id, timeout_sec=300.0)
        assert deployment.get("status") == "ready", pformat(deployment)

        session_id = require(client.agents.sessions.create(deployment_id), "id")
        session = client.agents.sessions.wait_until_running(session_id, timeout_sec=300.0)
        assert session.get("status") == "running", pformat(session)

        with OSM_SENSOR_LOG.open() as f:
            rows = list(csv.reader(f))[1 : 1 + ROWS_PER_QUERY]
        channels = [[float(row[column]) for row in rows] for column in range(1, len(rows[0]))]
        payload = {"query": "", "events": [{"type": "data.numeric_array", "event_data": {"contents": channels}}]}
        answer = client.agents.sessions.query(session_id, payload)
        assert answer.get("status") == "completed", pformat(answer)
        assert "response" in answer, pformat(answer)
    finally:
        delete_run(client, session_id, deployment_id, package_id)
