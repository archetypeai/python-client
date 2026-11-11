from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from typing import Literal

import requests

from archetypeai._base import ApiBase
from archetypeai._common import DEFAULT_CLIENT, safely_extract_response_data
from archetypeai._errors import ApiError

# Statuses where a session, eval or optimization has finished and will not change state again.
TERMINAL_AGENT_STATUSES = ("completed", "failed", "cancelled")
# Statuses where a deployment can take sessions, or has ended and never will.
TERMINAL_DEPLOYMENT_STATUSES = ("ready", "stopped", "failed")
# Statuses where a package build has finished and will not change state again.
TERMINAL_PACKAGE_STATUSES = ("ready", "failed")
# Query statuses that mean "busy or not ready yet, send the same query again later".
RETRYABLE_QUERY_STATUSES = (429, 503)
# Upper bound on one wait between query attempts, whatever Retry-After asks for.
MAX_QUERY_RETRY_DELAY_SEC = 30.0

# Where a package runs. `edge` is not available yet.
PackageTarget = Literal["platform", "edge"]
# How a package list is ranked.
PackageSort = Literal["created_at", "last_run_at", "name"]
SortOrder = Literal["asc", "desc"]
# How a deployment runs its sessions.
DeploymentKind = Literal["batch", "serving"]


def _drop_missing(params: dict) -> dict:
    """Removes any unset (None) entries so they are not sent to the API."""
    return {key: value for key, value in params.items() if value is not None}


def _query_params(params: dict) -> dict:
    """Like `_drop_missing`, for a query string: bools become `true`/`false`.

    The API rejects the `True` that requests would otherwise send. JSON bodies keep real bools.
    """
    return {
        key: str(value).lower() if isinstance(value, bool) else value for key, value in _drop_missing(params).items()
    }


def _as_data_ref(ref: str | dict) -> dict:
    """Converts a plain file ID into a data ref, passing dicts through untouched."""
    if isinstance(ref, str):
        return {"type": "file", "id": ref}
    return ref


def _as_example(example: str | dict) -> dict:
    """Converts a plain file ID into an eval example, passing dicts through untouched."""
    if isinstance(example, str):
        return {"inputs": [_as_data_ref(example)]}
    return example


def _retry_after_sec(response: requests.Response, default: float) -> float:
    """Reads a Retry-After header given in seconds, falling back to default when absent or not a number."""
    try:
        delay = float(response.headers.get("Retry-After", default))
    except ValueError:
        delay = default
    return min(max(delay, 0.0), MAX_QUERY_RETRY_DELAY_SEC)


def _wait_until_terminal(
    get_resource,
    resource_id: str,
    kind: str,
    poll_interval_sec: float,
    timeout_sec: float,
    describe=None,
    terminal_statuses: tuple[str, ...] = TERMINAL_AGENT_STATUSES,
) -> dict:
    """Polls a resource until it reaches a terminal status and returns it.

    Raises a TimeoutError if it is still running after timeout_sec seconds (a
    negative timeout waits forever). describe optionally renders extra progress
    detail for the periodic log line.
    """
    start_time = time.time()
    last_log_time = start_time
    while True:
        resource = get_resource(resource_id)
        status = resource.get("status")
        if status is None:
            raise ApiError(f"Malformed {kind} response, missing 'status': {resource}")
        if status in terminal_statuses:
            return resource
        elapsed = time.time() - start_time
        if timeout_sec >= 0 and elapsed >= timeout_sec:
            raise TimeoutError(f"{kind.capitalize()} {resource_id} did not complete within {timeout_sec} seconds")
        if time.time() - last_log_time >= 30.0:
            detail = f" {describe(resource)}" if describe else ""
            logging.info(f"{kind.capitalize()} {resource_id} is {status}{detail} ({int(elapsed)}s elapsed)")
            last_log_time = time.time()
        time.sleep(poll_interval_sec)


class _AgentApiBase(ApiBase):
    """Shared helpers for the agent API modules."""

    def __init__(self, api_key: str, api_endpoint: str, client: str = DEFAULT_CLIENT) -> None:
        super().__init__(api_key, api_endpoint, client=client)
        # 202 Accepted when launching an agent run; 204 No Content on deletes.
        self.valid_response_codes = (200, 201, 202, 204)

    def post_json(self, api_endpoint: str, data: dict) -> dict:
        """POSTs a JSON payload with the content-type header the agent API requires."""
        headers = {"Content-Type": "application/json"}
        return self.requests_post(api_endpoint, data_payload=json.dumps(data), additional_headers=headers)

    def patch_json(self, api_endpoint: str, data: dict) -> dict:
        """PATCHes a JSON payload, with the same retries and error handling as the other requests."""

        def patch() -> tuple[int, dict]:
            response = requests.patch(
                api_endpoint,
                data=json.dumps(data),
                headers={**self.auth_headers, "Content-Type": "application/json"},
                timeout=self.request_timeout_sec,
            )
            return response.status_code, safely_extract_response_data(response)

        return self._execute_request(request_func=patch, request_args={})


class BlueprintsApi(_AgentApiBase):
    """Main class for handling all agent blueprint API calls."""

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        key: str | None = None,
        canonical_only: bool | None = None,
        project_id: str | None = None,
    ) -> dict:
        """Lists the blueprints visible to your org, newest first.

        Use limit and after (the ID of the last item from the previous page) to paginate.
        Pass key to filter to a single blueprint key, e.g. `osm`.
        Pass canonical_only=True to leave out your org's own blueprints and list only the platform ones.
        Pass project_id (a `prj_` ID, or `none` for blueprints outside any project) to restrict to a project.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/blueprints")
        params = _query_params(
            {"limit": limit, "after": after, "key": key, "canonical_only": canonical_only, "project_id": project_id}
        )
        return self.requests_get(api_endpoint, params=params)

    def get(self, reference: str, include_yaml: bool | None = None, project_id: str | None = None) -> dict:
        """Gets a single blueprint by its `blp_` ID or key (e.g. `tva`).

        Pass include_yaml=True to always include the YAML rendering of the blueprint,
        or include_yaml=False to never include it. A key registered in a project
        resolves only when project_id names that project.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/blueprints/{reference}")
        params = _query_params({"yaml": include_yaml, "project_id": project_id})
        return self.requests_get(api_endpoint, params=params)

    def list_versions(
        self, reference: str, limit: int | None = None, after: str | None = None, project_id: str | None = None
    ) -> dict:
        """Lists all versions of a blueprint key, newest first."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/blueprints/{reference}/versions")
        params = _drop_missing({"limit": limit, "after": after, "project_id": project_id})
        return self.requests_get(api_endpoint, params=params)

    def copy(
        self,
        reference: str,
        project_id: str,
        blueprint_key: str,
        name: str | None = None,
        description: str | None = None,
        source_project_id: str | None = None,
        overrides: dict | None = None,
    ) -> dict:
        """Copies a blueprint into a project under a new key and returns the copy.

        This is how a platform blueprint, e.g. `osm`, gets into a project, where it
        can be packaged and deployed. reference is a `blp_` ID or a key; a key
        registered in a project resolves only when source_project_id names that
        project. blueprint_key must not be in use in the project, by your org's
        blueprints outside projects, or by a platform blueprint. name and
        description default to the original's. overrides sets values and models in
        the copy, e.g. `{"values": {"window_size": 360}}`.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/blueprints/{reference}/copy")
        payload = {"project_id": project_id, "blueprint_key": blueprint_key}
        payload.update(
            _drop_missing(
                {
                    "name": name,
                    "description": description,
                    "source_project_id": source_project_id,
                    "overrides": overrides,
                }
            )
        )
        return self.post_json(api_endpoint, payload)

    def create(
        self,
        blueprint_key: str,
        document: dict | None = None,
        yaml_document: str | None = None,
        project_id: str | None = None,
    ) -> dict:
        """Registers a blueprint under blueprint_key and returns it.

        Give the blueprint as document, as yaml_document, or both. Pass project_id to
        register it in a project, where it can be packaged and deployed. Requires the
        admin role, and is not available in the free trial: copy a platform blueprint
        into a project instead.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/blueprints")
        payload = {"blueprint_key": blueprint_key}
        payload.update(_drop_missing({"document": document, "yaml_document": yaml_document, "project_id": project_id}))
        return self.post_json(api_endpoint, payload)

    def delete(self, reference: str, project_id: str | None = None) -> dict:
        """Deletes a blueprint by its `blp_` ID, or the active version of a key.

        Whoever can modify a project can delete its blueprints. Deleting any other
        blueprint your org owns, such as one promoted outside a project, requires the
        admin role. The API refuses with a 409 while a package still holds the blueprint:
        delete it first.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/blueprints/{reference}")
        return self.requests_delete(api_endpoint, params=_drop_missing({"project_id": project_id}))


class PackagesApi(_AgentApiBase):
    """Main class for handling all agent package API calls.

    A package is an immutable build of a blueprint for a target. Building it
    resolves every model slot once, so a package always runs the same models,
    even if a model tag later moves. A package of a blueprint in a project is in
    that project; deploy a `ready` one with `client.agents.deployments.create`.
    """

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        before: str | None = None,
        blueprint_id: str | None = None,
        project_id: str | None = None,
        query: str | None = None,
        sort: PackageSort | None = None,
        order: SortOrder | None = None,
    ) -> dict:
        """Lists the packages in your org, newest first by default.

        Pass the previous page's next_cursor as after to fetch the next page, or the
        current page's prev_cursor as before to walk back. Pass blueprint_id to
        restrict to the packages holding a blueprint, project_id (a `prj_` ID, or
        `none` for packages outside any project) to restrict to a project, or query
        for a substring match over package names, descriptions and IDs. Pass sort
        (`created_at`, the default, `last_run_at` or `name`) and order (`asc` or `desc`) to
        change the ranking; keep both the same while paging.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/packages")
        params = _drop_missing(
            {
                "limit": limit,
                "after": after,
                "before": before,
                "blueprint_id": blueprint_id,
                "project_id": project_id,
                "query": query,
                "sort": sort,
                "order": order,
            }
        )
        return self.requests_get(api_endpoint, params=params)

    def get(self, package_id: str) -> dict:
        """Gets a single package by its `pkg_` ID, with what each model slot resolved to."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/packages/{package_id}")
        return self.requests_get(api_endpoint)

    def create(
        self, blueprint_id: str, target: PackageTarget = "platform", description: str = "", name: str | None = None
    ) -> dict:
        """Builds a package of a blueprint for a target and returns its metadata.

        Pass blueprint_id as a `blp_` ID. target is where the package will run:
        `platform` (the default) or `edge`, which is not available yet. name is the
        package's label, e.g. `Pump line 3`, and what its runs are called; omit it to
        name the package after its blueprint. The package comes back `building` or
        `ready`; call wait_until_ready before running it.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/packages")
        payload = {
            "blueprint_ids": [blueprint_id],
            "target": {"kind": target},
            "description": description,
        }
        if name is not None:
            payload["name"] = name
        return self.post_json(api_endpoint, payload)

    def delete(self, package_id: str) -> dict:
        """Deletes a package by its `pkg_` ID. The blueprint it holds is kept.

        The API refuses with a 409 while deployments of the package still exist:
        delete those first.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/packages/{package_id}")
        return self.requests_delete(api_endpoint)

    def wait_until_ready(self, package_id: str, poll_interval_sec: float = 2.0, timeout_sec: float = -1.0) -> dict:
        """Polls a package until its build is `ready` or `failed` and returns its metadata.

        Raises a TimeoutError if the package is still building after timeout_sec seconds
        (a negative timeout, the default, waits forever).
        """
        return _wait_until_terminal(
            self.get,
            package_id,
            "package",
            poll_interval_sec,
            timeout_sec,
            terminal_statuses=TERMINAL_PACKAGE_STATUSES,
        )


class DeploymentsApi(_AgentApiBase):
    """Main class for handling all agent deployment API calls.

    A deployment places a `ready` package so sessions can be opened on it: as a
    `batch` deployment, where each session is one run over its own input files,
    or as a `serving` deployment, where sessions send it queries. The package
    must be in a project; copy a platform blueprint into a project with
    `client.agents.blueprints.copy` before packaging it.
    """

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        before: str | None = None,
        project_id: str | None = None,
        package_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """Lists the deployments in your org, newest first.

        Pass the previous page's next_cursor as after to fetch the next page, or the
        current page's prev_cursor as before to walk back. Pass project_id,
        package_id, or status (e.g. `ready`) to filter.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/deployments")
        params = _drop_missing(
            {
                "limit": limit,
                "after": after,
                "before": before,
                "project_id": project_id,
                "package_id": package_id,
                "status": status,
            }
        )
        return self.requests_get(api_endpoint, params=params)

    def get(self, deployment_id: str) -> dict:
        """Gets a single deployment by its `dpl_` ID."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/deployments/{deployment_id}")
        return self.requests_get(api_endpoint)

    def create(self, package_id: str, kind: DeploymentKind = "batch") -> dict:
        """Deploys a `ready` package and returns the deployment's metadata.

        kind is `batch` (the default) or `serving`. The package must be built for the
        `platform` target and be in a project. A batch deployment is usually `ready`
        at once; a serving one is placed on a worker first. Call wait_until_ready
        before opening sessions on it.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/deployments")
        return self.post_json(api_endpoint, {"package_id": package_id, "kind": kind})

    def stop(self, deployment_id: str) -> dict:
        """Stops a deployment. Its open sessions are cancelled, and no new session can be opened on it."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/deployments/{deployment_id}/stop")
        return self.post_json(api_endpoint, {})

    def delete(self, deployment_id: str) -> dict:
        """Deletes a `stopped` or `failed` deployment by its `dpl_` ID.

        The API refuses with a 409 while the deployment is running or still has
        sessions: stop it and delete its sessions first.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/deployments/{deployment_id}")
        return self.requests_delete(api_endpoint)

    def wait_until_ready(self, deployment_id: str, poll_interval_sec: float = 2.0, timeout_sec: float = -1.0) -> dict:
        """Polls a deployment until it is `ready` and returns its metadata.

        Returns early if it ends instead, e.g. `failed` when it cannot be placed; check
        `status`, and `error` for the reason. Raises a TimeoutError if the deployment is
        still deploying after timeout_sec seconds (a negative timeout, the default, waits
        forever).
        """
        return _wait_until_terminal(
            self.get,
            deployment_id,
            "deployment",
            poll_interval_sec,
            timeout_sec,
            terminal_statuses=TERMINAL_DEPLOYMENT_STATUSES,
        )


class SessionsApi(_AgentApiBase):
    """Main class for handling all agent session API calls.

    A session runs on a `ready` deployment and takes its kind. A batch session is
    one run over its input files and finishes with results. A serving session
    stays open and answers queries until it is cancelled or its deployment ends.
    """

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        before: str | None = None,
        project_id: str | None = None,
        deployment_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """Lists the sessions in your org, newest first.

        Pass the previous page's next_cursor as after to fetch the next page, or the
        current page's prev_cursor as before to walk back. Pass project_id,
        deployment_id, or status (e.g. `running`) to filter.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/sessions")
        params = _drop_missing(
            {
                "limit": limit,
                "after": after,
                "before": before,
                "project_id": project_id,
                "deployment_id": deployment_id,
                "status": status,
            }
        )
        return self.requests_get(api_endpoint, params=params)

    def get(self, session_id: str) -> dict:
        """Gets a single session by its `ses_` ID."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/sessions/{session_id}")
        return self.requests_get(api_endpoint)

    def create(
        self,
        deployment_id: str,
        source: Sequence[str | dict] | None = None,
        sink: str | dict | None = None,
    ) -> dict:
        """Opens a session on a `ready` deployment and returns its metadata.

        A batch session needs at least one source entry. Each source entry is either
        a file ID or a data ref dict, e.g. {"type": "file", "id": "file_abc123",
        "format": "csv"}. By default the agent writes one output per input; pass sink
        to direct all output to a single ref. A serving session takes no source or
        sink: call wait_until_running, then send it requests with query.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/sessions")
        payload: dict = {"deployment_id": deployment_id}
        if source is not None or sink is not None:
            connectors: dict = {"source": [_as_data_ref(ref) for ref in source or []]}
            if sink is not None:
                connectors["sink"] = _as_data_ref(sink)
            payload["connectors"] = connectors
        return self.post_json(api_endpoint, payload)

    def get_events(
        self, session_id: str, limit: int | None = None, after: str | None = None, before: str | None = None
    ) -> dict:
        """Gets the lifecycle events of a session, newest first.

        Pass the previous page's next_cursor as after to fetch the next page.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/sessions/{session_id}/events")
        params = _drop_missing({"limit": limit, "after": after, "before": before})
        return self.requests_get(api_endpoint, params=params)

    def get_results(
        self, session_id: str, limit: int | None = None, after: str | None = None, before: str | None = None
    ) -> dict:
        """Gets the output files produced by a batch session, newest first.

        Pass the previous page's next_cursor as after to fetch the next page. A serving
        session has no output files: the API refuses with a 409.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/sessions/{session_id}/results")
        params = _drop_missing({"limit": limit, "after": after, "before": before})
        return self.requests_get(api_endpoint, params=params)

    def cancel(self, session_id: str) -> dict:
        """Cancels a pending or running session. Its deployment and other sessions are not affected."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/sessions/{session_id}/cancel")
        return self.post_json(api_endpoint, {})

    def pause(self, session_id: str) -> dict:
        """Pauses a running session."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/sessions/{session_id}/pause")
        return self.post_json(api_endpoint, {})

    def resume(self, session_id: str) -> dict:
        """Resumes a paused session."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/sessions/{session_id}/resume")
        return self.post_json(api_endpoint, {})

    def delete(self, session_id: str) -> dict:
        """Deletes an ended session by its `ses_` ID. Cancel a session that has not ended first."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/sessions/{session_id}")
        return self.requests_delete(api_endpoint)

    def wait_until_done(self, session_id: str, poll_interval_sec: float = 5.0, timeout_sec: float = -1.0) -> dict:
        """Polls a batch session until it reaches a terminal status and returns its metadata.

        Raises a TimeoutError if the session is still running after timeout_sec seconds
        (a negative timeout, the default, waits forever). Raises a ValueError for a
        serving session, which stays `running` instead of finishing: use wait_until_running.
        """
        if self.get(session_id).get("kind") == "serving":
            raise ValueError(f"Session {session_id} is a serving session and does not finish; use wait_until_running")
        return _wait_until_terminal(self.get, session_id, "session", poll_interval_sec, timeout_sec)

    def wait_until_running(self, session_id: str, poll_interval_sec: float = 2.0, timeout_sec: float = -1.0) -> dict:
        """Polls a serving session until it is `running` and returns its metadata.

        A serving session answers queries once it is `running`. Returns early if it ends
        instead, e.g. `failed` or `cancelled` when its deployment ends; check `status`, and
        `error` for the reason. Raises a TimeoutError if the session is still pending after
        timeout_sec seconds (a negative timeout, the default, waits forever).
        """
        return _wait_until_terminal(
            self.get,
            session_id,
            "session",
            poll_interval_sec,
            timeout_sec,
            terminal_statuses=("running", *TERMINAL_AGENT_STATUSES),
        )

    def query(self, session_id: str, payload: dict, max_retries: int = 3) -> dict:
        """Sends one request to a `running` serving session and returns its answer.

        payload is whatever the agent's blueprint accepts, and the answer's `response`
        is whatever the blueprint produces. When the agent is busy (429) or not ready
        yet (503), the query is sent again up to max_retries times, waiting as long as
        the server's Retry-After asks, or 1s, 2s, 4s, ... without one. Every other
        error raises an ApiError at once: a 504 means the agent ran out of time, and
        sending the same query again would run it again.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/sessions/{session_id}/query")
        headers = {**self.auth_headers, "Content-Type": "application/json"}
        attempt = 0
        while True:
            response = requests.post(
                api_endpoint, data=json.dumps(payload), headers=headers, timeout=self.request_timeout_sec
            )
            if response.status_code == 200:
                return safely_extract_response_data(response)
            if response.status_code not in RETRYABLE_QUERY_STATUSES or attempt >= max_retries:
                raise ApiError(safely_extract_response_data(response))
            delay = _retry_after_sec(response, default=float(2**attempt))
            logging.info(f"Session {session_id} answered {response.status_code}, retrying the query in {delay:.0f}s")
            time.sleep(delay)
            attempt += 1


class EvalsApi(_AgentApiBase):
    """Main class for handling all eval API calls.

    An eval scores a blueprint on labeled examples and reports its metrics, e.g.
    the macro F1 of an OSM blueprint's predicted states, or of an AD blueprint's
    `normal` / `anomaly` window labels.
    """

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        before: str | None = None,
        status: str | None = None,
        query: str | None = None,
        blueprint_id: str | None = None,
        project_id: str | None = None,
    ) -> dict:
        """Lists the evals in your org, newest first.

        Pass the previous page's next_cursor as after to fetch the next page. Pass
        status (e.g. `running`), query (substring match), blueprint_id, or project_id
        (a `prj_` ID, or `none` for those outside any project) to filter.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/evals")
        params = _drop_missing(
            {
                "limit": limit,
                "after": after,
                "before": before,
                "status": status,
                "query": query,
                "blueprint_id": blueprint_id,
                "project_id": project_id,
            }
        )
        return self.requests_get(api_endpoint, params=params)

    def get(self, eval_id: str) -> dict:
        """Gets a single eval by its `evl_` ID, with its metrics report once completed."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/evals/{eval_id}")
        return self.requests_get(api_endpoint)

    def create(
        self,
        blueprint_id: str,
        examples: list[str | dict],
        name: str = "",
        primary: str | None = None,
        targets: dict | None = None,
        emit_predictions: bool | None = None,
        constraints: list[dict] | None = None,
    ) -> dict:
        """Creates and starts an eval of a blueprint, and returns its metadata.

        Pass blueprint_id as a `blp_` ID. Each example is either a file ID or an
        example dict, e.g. {"inputs": [{"type": "file", "id": "file_abc123"}],
        "ground_truth": {...}}. A file ID alone works when the file carries its
        labels in a column named after the target, e.g. `state` for OSM.
        primary (e.g. `state.macro_f1`) and targets override the blueprint's
        scoring defaults for this run. constraints replaces the blueprint's
        bounds, which the run reports a verdict on, e.g. [{"objective":
        "state.recall_idle", "min": 0.6}]; [] means none.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/evals")
        payload: dict = {
            "blueprint_id": blueprint_id,
            "examples": [_as_example(example) for example in examples],
            "name": name,
        }
        payload.update(
            _drop_missing(
                {
                    "primary": primary,
                    "targets": targets,
                    "emit_predictions": emit_predictions,
                    "constraints": constraints,
                }
            )
        )
        return self.post_json(api_endpoint, payload)

    def list_examples(
        self, eval_id: str, limit: int | None = None, after: str | None = None, before: str | None = None
    ) -> dict:
        """Lists what an eval measured for each of its examples, in the order they were given."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/evals/{eval_id}/examples")
        params = _drop_missing({"limit": limit, "after": after, "before": before})
        return self.requests_get(api_endpoint, params=params)

    def cancel(self, eval_id: str) -> dict:
        """Cancels a pending or running eval."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/evals/{eval_id}/cancel")
        return self.post_json(api_endpoint, {})

    def delete(self, eval_id: str) -> dict:
        """Deletes a finished eval and the files it produced."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/evals/{eval_id}")
        return self.requests_delete(api_endpoint)

    def wait_until_done(self, eval_id: str, poll_interval_sec: float = 10.0, timeout_sec: float = -1.0) -> dict:
        """Polls an eval until it reaches a terminal status and returns its metadata.

        Raises a TimeoutError if the eval is still running after timeout_sec seconds
        (a negative timeout, the default, waits forever).
        """
        return _wait_until_terminal(self.get, eval_id, "eval", poll_interval_sec, timeout_sec)


def _describe_progress(optimization: dict) -> str:
    """Renders an optimization's trial counts for the periodic log line."""
    progress = optimization.get("progress") or {}
    counts = ", ".join(f"{count} {state}" for state, count in progress.items() if count)
    return f"(trials: {counts})" if counts else ""


class OptimizationsApi(_AgentApiBase):
    """Main class for handling all optimization API calls.

    An optimization searches a blueprint's values: each trial fits the blueprint
    on the training examples and scores it on the validation examples. Promote
    the winning trial to get a blueprint of your own, ready to package and deploy.
    """

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        before: str | None = None,
        status: str | None = None,
        query: str | None = None,
        blueprint_id: str | None = None,
        project_id: str | None = None,
    ) -> dict:
        """Lists the optimizations in your org, newest first.

        Pass the previous page's next_cursor as after to fetch the next page. Pass
        status (e.g. `running`), query (substring match), blueprint_id, or project_id
        (a `prj_` ID, or `none` for those outside any project) to filter.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/optimizations")
        params = _drop_missing(
            {
                "limit": limit,
                "after": after,
                "before": before,
                "status": status,
                "query": query,
                "blueprint_id": blueprint_id,
                "project_id": project_id,
            }
        )
        return self.requests_get(api_endpoint, params=params)

    def get(self, optimization_id: str) -> dict:
        """Gets a single optimization by its `opt_` ID, with its trial progress and best trial."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/optimizations/{optimization_id}")
        return self.requests_get(api_endpoint)

    def create(
        self,
        blueprint_id: str,
        objective: str | None,
        validation_examples: list[str | dict],
        max_trials: int,
        training_examples: list[str | dict] | None = None,
        calibration_examples: list[str | dict] | None = None,
        search_space: dict | None = None,
        overrides: dict | None = None,
        constraints: list[dict] | dict | None = None,
        name: str = "",
        primary: str | None = None,
        targets: dict | None = None,
    ) -> dict:
        """Creates and starts an optimization of a blueprint, and returns its metadata.

        Pass blueprint_id as a `blp_` ID. The run maximizes primary, e.g.
        `state.macro_f1`, or the blueprint's own headline when neither primary
        nor objective is given; objective is the deprecated way of naming one of
        the headline target's metrics, e.g. `macro_f1`, and must be None when
        primary is given. targets overrides the blueprint's scoring defaults for
        every trial, as for evals. Examples take the same form as for evals. The
        run spends at most max_trials trials sampling search_space, e.g.
        {"parameters": {"k_neighbors": {"kind": "value", "spec": {"type":
        "categorical", "values": [5, 31]}}}}. overrides sets blueprint values or
        models for every trial, e.g. {"values": {"states": ["idle", "running"]}};
        values the blueprint marks as required must be set here. constraints
        replaces the blueprint's bounds, which a trial must meet to be the run's
        best, e.g. [{"objective": "state.recall_idle", "min": 0.6}]; [] means
        none. The earlier {"min_metric": [{"metric": "recall", "class": "idle",
        "min_value": 0.6}]} form is still accepted.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/optimizations")
        payload: dict = {
            "blueprint_id": blueprint_id,
            "validation_examples": [_as_example(example) for example in validation_examples],
            "budget": {"max_trials": max_trials},
            "name": name,
        }
        if training_examples is not None:
            payload["training_examples"] = [_as_example(example) for example in training_examples]
        if calibration_examples is not None:
            payload["calibration_examples"] = [_as_example(example) for example in calibration_examples]
        payload.update(
            _drop_missing(
                {
                    "objective": objective,
                    "primary": primary,
                    "targets": targets,
                    "search_space": search_space,
                    "overrides": overrides,
                    "constraints": constraints,
                }
            )
        )
        return self.post_json(api_endpoint, payload)

    def list_trials(
        self,
        optimization_id: str,
        limit: int | None = None,
        after: str | None = None,
        before: str | None = None,
        status: str | None = None,
    ) -> dict:
        """Lists an optimization's trials, newest first, with each one's sampled values and scores."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/optimizations/{optimization_id}/trials")
        params = _drop_missing({"limit": limit, "after": after, "before": before, "status": status})
        return self.requests_get(api_endpoint, params=params)

    def promote_trial(
        self,
        optimization_id: str,
        trial_id: str,
        blueprint_key: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Promotes a completed trial to a blueprint of your own and returns that blueprint.

        The blueprint carries the trial's values and fitted models. By default it is
        keyed after the searched blueprint and the trial's ID, and keeps the searched
        blueprint's name and description.
        """
        api_endpoint = self._get_endpoint(
            self.api_endpoint, f"agents/optimizations/{optimization_id}/trials/{trial_id}/promote"
        )
        payload = _drop_missing({"blueprint_key": blueprint_key, "name": name, "description": description})
        return self.post_json(api_endpoint, payload)

    def cancel(self, optimization_id: str) -> dict:
        """Cancels a pending or running optimization and its unfinished trials."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/optimizations/{optimization_id}/cancel")
        return self.post_json(api_endpoint, {})

    def delete(self, optimization_id: str) -> dict:
        """Deletes a finished optimization and its trials. Promoted blueprints are kept."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/optimizations/{optimization_id}")
        return self.requests_delete(api_endpoint)

    def wait_until_done(self, optimization_id: str, poll_interval_sec: float = 30.0, timeout_sec: float = -1.0) -> dict:
        """Polls an optimization until it reaches a terminal status and returns its metadata.

        Logs trial progress while it runs. Raises a TimeoutError if the run is still
        going after timeout_sec seconds (a negative timeout, the default, waits forever).
        """
        return _wait_until_terminal(
            self.get, optimization_id, "optimization", poll_interval_sec, timeout_sec, _describe_progress
        )


class AgentsApi(ApiBase):
    """Main class for handling all agent API calls.

    An agent goes through a blueprint -> package -> deployment -> session lifecycle,
    inside a project (`client.projects`):
    - blueprints: the reusable agent definition. Copy a platform blueprint
      (e.g. `osm` or `mga`) into your project to run it.
    - packages: an immutable build of a blueprint for a target, with every
      model slot resolved
    - deployments: a package placed as `batch` or `serving`
    - sessions: a batch run over your input files, or a serving connection
      that answers queries

    Evals score a blueprint on labeled data; optimizations search a blueprint's
    values and fit its models, and promote the best trial to a new blueprint.
    """

    blueprints: BlueprintsApi
    packages: PackagesApi
    deployments: DeploymentsApi
    sessions: SessionsApi
    evals: EvalsApi
    optimizations: OptimizationsApi

    def __init__(self, api_key: str, api_endpoint: str, client: str = DEFAULT_CLIENT) -> None:
        super().__init__(api_key, api_endpoint, client=client)
        self.blueprints = BlueprintsApi(api_key, api_endpoint, client=client)
        self.packages = PackagesApi(api_key, api_endpoint, client=client)
        self.deployments = DeploymentsApi(api_key, api_endpoint, client=client)
        self.sessions = SessionsApi(api_key, api_endpoint, client=client)
        self.evals = EvalsApi(api_key, api_endpoint, client=client)
        self.optimizations = OptimizationsApi(api_key, api_endpoint, client=client)

    def get_node_registry(self) -> dict:
        """Gets the registry of connector and processing nodes available to blueprints."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/nodes/registry")
        return self.requests_get(api_endpoint)
