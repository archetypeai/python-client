# Shared helpers for the agent examples: safe handling of API responses, the
# project the examples run in, the package -> deployment -> session lifecycle,
# and input file upload.
import csv
import gzip
import logging
import os
import shutil
import tempfile

from archetypeai import ApiError, ArchetypeAI, DeploymentKind, pformat

# The project every example runs in. It is created on first use and reused after.
EXAMPLES_PROJECT_NAME = "Python client examples"


def require(response: dict, key: str):
    """Returns a required field of an API response, failing with the full response if it is missing."""
    value = response.get(key)
    assert value, f"Malformed API response, missing '{key}': {pformat(response)}"
    return value


def get_or_create_project(client: ArchetypeAI, name: str = EXAMPLES_PROJECT_NAME) -> str:
    """Returns the ID of your project of that name, creating it if it does not exist yet."""
    after = None
    while True:
        page = client.projects.list(after=after)
        for project in page.get("data", []):
            if project.get("name", "").lower() == name.lower():
                return require(project, "id")
        after = page.get("next_cursor")
        if not after:
            break
    project_id = require(client.projects.create(name), "id")
    logging.info(f"Created project_id: {project_id}")
    return project_id


def get_or_copy_blueprint(
    client: ArchetypeAI, project_id: str, reference: str, blueprint_key: str, overrides: dict | None = None
) -> str:
    """Returns the ID of the project's blueprint_key, copying reference (e.g. `mga`) under that key if absent.

    Only a blueprint in a project can be packaged and deployed, so a platform
    blueprint is copied into the project first. overrides apply to a new copy only.
    """
    try:
        return require(client.agents.blueprints.get(blueprint_key, project_id=project_id), "id")
    except ApiError:
        copy = client.agents.blueprints.copy(
            reference, project_id=project_id, blueprint_key=blueprint_key, overrides=overrides
        )
        blueprint_id = require(copy, "id")
        logging.info(f"Copied {reference} into the project as {blueprint_key}: {blueprint_id}")
        return blueprint_id


def build_package(client: ArchetypeAI, blueprint_id: str, name: str) -> str:
    """Builds a package of a blueprint, waits until it is ready, and returns its ID."""
    created = client.agents.packages.create(blueprint_id, name=name)
    package = client.agents.packages.wait_until_ready(require(created, "id"))
    package_id = require(package, "id")
    assert package.get("status") == "ready", f"Package {package_id} did not build: {pformat(package)}"
    logging.info(f"Built package_id: {package_id}")
    return package_id


def deploy(client: ArchetypeAI, package_id: str, kind: DeploymentKind = "batch") -> str:
    """Deploys a package as `batch` or `serving`, waits until it is ready, and returns its ID."""
    created = client.agents.deployments.create(package_id, kind=kind)
    deployment = client.agents.deployments.wait_until_ready(require(created, "id"))
    deployment_id = require(deployment, "id")
    assert deployment.get("status") == "ready", f"Deployment {deployment_id} is not ready: {pformat(deployment)}"
    logging.info(f"Deployed {kind} deployment_id: {deployment_id}")
    return deployment_id


def run_batch_session(client: ArchetypeAI, deployment_id: str, source: list, max_run_time_sec: float) -> str:
    """Runs a batch session over source, logs its results or events, and returns its ID."""
    session = client.agents.sessions.create(deployment_id, source=source)
    session_id = require(session, "id")
    logging.info(f"Opened session_id: {session_id} status: {session.get('status')}")

    # Wait for the session to reach a terminal state (completed, failed, or cancelled).
    session = client.agents.sessions.wait_until_done(session_id, timeout_sec=max_run_time_sec)
    status = session.get("status")
    logging.info(f"Session finished with status: {status}")
    if status == "completed":
        results = client.agents.sessions.get_results(session_id)
        logging.info(f"Session results: {pformat(results)}")
    else:
        # Log the session's event log to help debug the failure.
        events = client.agents.sessions.get_events(session_id)
        logging.error(f"Session did not complete: {pformat(events)}")
    return session_id


def read_channels(path: str) -> list[list[float]]:
    """Reads a plain or gzipped sensor CSV as one list of values per data column, leaving out the leading timestamp."""
    with gzip.open(path, "rt") if path.endswith(".gz") else open(path) as f:
        rows = list(csv.reader(f))[1:]
    return [[float(row[column]) for row in rows] for column in range(1, len(rows[0]))]


def run_serving_session(
    client: ArchetypeAI,
    deployment_id: str,
    channels: list[list[float]],
    rows_per_query: int,
    num_queries: int,
    max_wait_time_sec: float,
) -> str:
    """Opens a serving session, queries it with the first num_queries slices of channels, and returns its ID.

    Each query carries rows_per_query rows inline: one list of values per data column.
    """
    session = client.agents.sessions.create(deployment_id)
    session_id = require(session, "id")
    session = client.agents.sessions.wait_until_running(session_id, timeout_sec=max_wait_time_sec)
    if session.get("status") != "running":
        events = client.agents.sessions.get_events(session_id)
        logging.error(f"Session {session_id} is not running: {pformat(events)}")
        return session_id
    logging.info(f"Serving session {session_id} is running")

    for start in range(0, min(len(channels[0]), rows_per_query * num_queries), rows_per_query):
        rows = [channel[start : start + rows_per_query] for channel in channels]
        query = {"query": "", "events": [{"type": "data.numeric_array", "event_data": {"contents": rows}}]}
        answer = client.agents.sessions.query(session_id, query)
        logging.info(f"Rows {start}-{start + len(rows[0]) - 1}: {answer.get('query_response_time_ms')} ms")
        # One entry per agent window. Lists, such as embeddings, are left out of the log.
        for window in (answer.get("response") or {}).get("data", []):
            logging.info(f"  { ({key: value for key, value in window.items() if not isinstance(value, list)}) }")
    return session_id


def tear_down(
    client: ArchetypeAI,
    session_ids: list[str] | None = None,
    deployment_id: str | None = None,
    package_id: str | None = None,
) -> None:
    """Deletes sessions, then the deployment, then the package, so repeated runs do not accumulate them.

    Each one blocks deleting the next: a deployment with sessions, or a package with
    deployments, cannot be deleted. The project and its blueprints are kept for reuse.
    """
    for session_id in session_ids or []:
        if client.agents.sessions.get(session_id).get("status") not in ("completed", "failed", "cancelled"):
            client.agents.sessions.cancel(session_id)
        client.agents.sessions.delete(session_id)
    if deployment_id:
        if client.agents.deployments.get(deployment_id).get("status") not in ("stopped", "failed"):
            client.agents.deployments.stop(deployment_id)
        # Wait for the deployment to reach `stopped`: only an ended one can be deleted.
        client.agents.deployments.wait_until_ready(deployment_id)
        client.agents.deployments.delete(deployment_id)
    if package_id:
        client.agents.packages.delete(package_id)


def run_batch(
    client: ArchetypeAI,
    blueprint_id: str,
    package_name: str,
    source: list,
    max_run_time_sec: float,
) -> None:
    """Runs a project blueprint once over source, then deletes what the run created.

    The blueprint is packaged and deployed as `batch`; one session then runs over source.
    """
    package_id = build_package(client, blueprint_id, package_name)
    deployment_id = None
    session_ids = []
    try:
        deployment_id = deploy(client, package_id, kind="batch")
        session_id = run_batch_session(client, deployment_id, source, max_run_time_sec)
        session_ids.append(session_id)
    finally:
        tear_down(client, session_ids, deployment_id, package_id)


def delete_deployment(client: ArchetypeAI, deployment_id: str) -> None:
    """Deletes a deployment and every session on it, including one whose ID a failed step never returned."""
    sessions = client.agents.sessions.list(deployment_id=deployment_id).get("data", [])
    tear_down(client, [require(session, "id") for session in sessions], deployment_id)


def run_batch_and_serving(
    client: ArchetypeAI,
    package_id: str,
    source: list,
    channels: list[list[float]],
    rows_per_query: int,
    num_queries: int,
    max_run_time_sec: float,
) -> None:
    """Runs a package as batch over source, then serves it and queries it with channels.

    Each deployment is deleted before the next one starts. The package is deleted last.
    """
    try:
        deployment_id = None
        try:
            deployment_id = deploy(client, package_id, kind="batch")
            run_batch_session(client, deployment_id, source, max_run_time_sec)
        finally:
            if deployment_id:
                delete_deployment(client, deployment_id)

        deployment_id = None
        try:
            deployment_id = deploy(client, package_id, kind="serving")
            run_serving_session(client, deployment_id, channels, rows_per_query, num_queries, max_run_time_sec)
        finally:
            if deployment_id:
                delete_deployment(client, deployment_id)
    finally:
        tear_down(client, package_id=package_id)


def get_or_upload_file(client: ArchetypeAI, filename: str) -> str:
    """Uses the file if it is already on the platform, otherwise uploads it.

    The platform reads plain CSV, so a gzipped file is unpacked first and uploaded
    without its `.gz` suffix.
    """
    file_id = os.path.basename(filename).removesuffix(".gz")
    try:
        client.files.get_metadata(file_id=file_id)
        logging.info(f"Input file already on the platform: {file_id}")
    except ApiError:
        with tempfile.TemporaryDirectory() as scratch_dir:
            if filename.endswith(".gz"):
                unpacked = os.path.join(scratch_dir, file_id)
                with gzip.open(filename, "rb") as packed, open(unpacked, "wb") as out:
                    shutil.copyfileobj(packed, out)
                filename = unpacked
            file_id = require(client.files.local.upload(filename), "file_id")
        logging.info(f"Uploaded input file: {file_id}")
    return file_id
