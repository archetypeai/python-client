from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlparse

from archetypeai._base import ApiBase
from archetypeai._errors import ApiError

# Statuses where an agent has finished and will not change state again.
TERMINAL_AGENT_STATUSES = ("completed", "failed", "canceled")


def _default_agent_endpoint(api_endpoint: str) -> str:
    """Returns the endpoint root (scheme + host) the agent API is served from.

    The agent API is versionless (e.g. https://api.archetypeai.app/agents), unlike
    the versioned APIs (e.g. https://api.archetypeai.app/v0.5/files).
    """
    parsed = urlparse(api_endpoint)
    return f"{parsed.scheme}://{parsed.netloc}"


def _drop_missing(params: dict) -> dict:
    """Removes unset (None) entries and renders booleans the way the API expects.

    The query-string deserialiser accepts only lowercase `true` / `false`. A
    Python bool passed through verbatim is serialised as "True", which the API
    rejects:

        GET /agents/blueprints/tva?yaml=True
        -> 400 Failed to deserialize query string: yaml: provided string was
               not `true` or `false`
        GET /agents/blueprints/tva?yaml=true
        -> 200

    Callers see that as an empty ApiError, so the cause is invisible from the
    client side. Normalise here rather than at each call site, so any boolean
    parameter added later is correct by default.
    """
    normalised = {}
    for key, value in params.items():
        if value is None:
            continue
        normalised[key] = str(value).lower() if isinstance(value, bool) else value
    return normalised


def _as_data_ref(ref: str | dict) -> dict:
    """Converts a plain file ID into a data ref, passing dicts through untouched."""
    if isinstance(ref, str):
        return {"type": "file", "id": ref}
    return ref


class _AgentApiBase(ApiBase):
    """Shared helpers for the agent API modules."""

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)
        # 202 Accepted when launching an agent run; 204 No Content on deletes.
        self.valid_response_codes = (200, 201, 202, 204)

    def post_json(self, api_endpoint: str, data: dict) -> dict:
        """POSTs a JSON payload with the content-type header the agent API requires."""
        headers = {"Content-Type": "application/json"}
        return self.requests_post(api_endpoint, data_payload=json.dumps(data), additional_headers=headers)


class BlueprintsApi(_AgentApiBase):
    """Main class for handling all agent blueprint API calls."""

    def list(self, limit: int | None = None, after: str | None = None, key: str | None = None) -> dict:
        """Lists the blueprints visible to your org, newest first.

        Use limit and after (the ID of the last item from the previous page) to paginate.
        Pass key to filter to a single blueprint key, e.g. `osm`.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/blueprints")
        params = _drop_missing({"limit": limit, "after": after, "key": key})
        return self.requests_get(api_endpoint, params=params)

    def get(self, reference: str, include_yaml: bool | None = None) -> dict:
        """Gets a single blueprint by its `blp_` ID or key (e.g. `tva`).

        Pass include_yaml=True to always include the YAML rendering of the blueprint,
        or include_yaml=False to never include it.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/blueprints/{reference}")
        params = _drop_missing({"yaml": include_yaml})
        return self.requests_get(api_endpoint, params=params)

    def list_versions(self, reference: str, limit: int | None = None, after: str | None = None) -> dict:
        """Lists all versions of a blueprint key, newest first."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/blueprints/{reference}/versions")
        params = _drop_missing({"limit": limit, "after": after})
        return self.requests_get(api_endpoint, params=params)


class BundlesApi(_AgentApiBase):
    """Main class for handling all agent bundle API calls.

    A bundle pins a blueprint (and optional values/artifacts) so it is ready to
    run. Some agents ship with platform-hosted quick-start bundles; others create
    an org-owned bundle from a canonical blueprint at deploy time.
    """

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        query: str | None = None,
        blueprint_id: str | None = None,
    ) -> dict:
        """Lists the bundles in your org, newest first.

        Pass query for a substring match over bundle names and IDs, or blueprint_id
        to restrict to bundles built from a specific blueprint.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/bundles")
        params = _drop_missing({"limit": limit, "after": after, "query": query, "blueprint_id": blueprint_id})
        return self.requests_get(api_endpoint, params=params)

    def get(self, bundle_id: str) -> dict:
        """Gets a single bundle by its `bnd_` ID."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/bundles/{bundle_id}")
        return self.requests_get(api_endpoint)

    def create(
        self,
        blueprint: str,
        name: str,
        description: str = "",
        model: str | None = None,
        values: dict | None = None,
        artifacts: dict | None = None,
    ) -> dict:
        """Creates a bundle pinned to a blueprint and returns its metadata.

        Pass blueprint as a `blp_` id or key (e.g. `mga`). Bundles are created
        ready to run and are owned by your org.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/bundles")
        payload: dict = {
            "blueprint": blueprint,
            "name": name,
            "description": description,
        }
        if model is not None:
            payload["model"] = model
        if values is not None:
            payload["values"] = values
        if artifacts is not None:
            payload["artifacts"] = artifacts
        return self.post_json(api_endpoint, payload)

    def delete(self, bundle_id: str) -> dict:
        """Deletes a bundle by its `bnd_` ID."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/bundles/{bundle_id}")
        return self.requests_delete(api_endpoint)

    def run(self, bundle_id: str, source: list[str | dict], sink: str | dict | None = None) -> dict:
        """Runs a bundle, launching a new agent instance, and returns its metadata.

        Each source entry is either a file ID or a data ref dict, e.g.
        {"type": "file", "id": "file_abc123", "format": "csv"}. The input data must
        match the format the bundle was built for. By default the agent writes one
        output per input; pass sink to direct all output to a single ref.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/bundles/{bundle_id}/run")
        connectors = {"source": [_as_data_ref(ref) for ref in source]}
        if sink is not None:
            connectors["sink"] = _as_data_ref(sink)
        return self.post_json(api_endpoint, {"connectors": connectors})


class InstancesApi(_AgentApiBase):
    """Main class for handling all agent instance API calls."""

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        status: str | None = None,
        query: str | None = None,
        bundle_id: str | None = None,
        blueprint_id: str | None = None,
    ) -> dict:
        """Lists the agent instances in your org, newest first.

        Pass status (e.g. `running`), query (substring match), bundle_id, or
        blueprint_id to filter the results.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/instances")
        params = _drop_missing(
            {
                "limit": limit,
                "after": after,
                "status": status,
                "query": query,
                "bundle_id": bundle_id,
                "blueprint_id": blueprint_id,
            }
        )
        return self.requests_get(api_endpoint, params=params)

    def get(self, agent_id: str) -> dict:
        """Gets a single agent instance by its `agt_` ID."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/instances/{agent_id}")
        return self.requests_get(api_endpoint)

    def get_events(self, agent_id: str) -> dict:
        """Gets the lifecycle event log of an agent instance."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/instances/{agent_id}/events")
        return self.requests_get(api_endpoint)

    def get_results(self, agent_id: str, limit: int | None = None, after: str | None = None) -> dict:
        """Gets the output refs produced by an agent instance, newest first.

        Pass the previous page's next_cursor as after to fetch the next page.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/instances/{agent_id}/results")
        params = _drop_missing({"limit": limit, "after": after})
        return self.requests_get(api_endpoint, params=params)

    def get_logs(
        self,
        agent_id: str,
        limit: int | None = None,
        after: str | None = None,
        level: str | None = None,
        search: str | None = None,
    ) -> dict:
        """Gets the run logs of an agent instance, newest first.

        Pass the previous page's next_cursor as after to fetch the next page. Narrow with
        level (e.g. `error`) or search (substring match on message and event type).
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/instances/{agent_id}/logs")
        params = _drop_missing({"limit": limit, "after": after, "level": level, "search": search})
        return self.requests_get(api_endpoint, params=params)

    def cancel(self, agent_id: str) -> dict:
        """Cancels a running or paused agent instance."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/instances/{agent_id}/cancel")
        return self.post_json(api_endpoint, {})

    def pause(self, agent_id: str) -> dict:
        """Pauses a running agent instance."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/instances/{agent_id}/pause")
        return self.post_json(api_endpoint, {})

    def resume(self, agent_id: str) -> dict:
        """Resumes a paused agent instance."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/instances/{agent_id}/resume")
        return self.post_json(api_endpoint, {})

    def delete(self, agent_id: str) -> dict:
        """Deletes an agent instance by its `agt_` ID."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"agents/instances/{agent_id}")
        return self.requests_delete(api_endpoint)

    def wait_until_done(self, agent_id: str, poll_interval_sec: float = 5.0, timeout_sec: float = -1.0) -> dict:
        """Polls an agent instance until it reaches a terminal status and returns its metadata.

        Raises a TimeoutError if the agent is still running after timeout_sec seconds
        (a negative timeout, the default, waits forever).
        """
        start_time = time.time()
        last_log_time = start_time
        while True:
            agent = self.get(agent_id)
            status = agent.get("status")
            if status is None:
                raise ApiError(f"Malformed agent response, missing 'status': {agent}")
            if status in TERMINAL_AGENT_STATUSES:
                return agent
            elapsed = time.time() - start_time
            if timeout_sec >= 0 and elapsed >= timeout_sec:
                raise TimeoutError(f"Agent {agent_id} did not complete within {timeout_sec} seconds")
            if time.time() - last_log_time >= 30.0:
                logging.info(f"Agent {agent_id} is {status} ({int(elapsed)}s elapsed)")
                last_log_time = time.time()
            time.sleep(poll_interval_sec)


class AgentsApi(ApiBase):
    """Main class for handling all agent API calls.

    The agent platform follows a develop -> deploy -> execute lifecycle:
    - develop: blueprints — the reusable agent definition
      (e.g. the canonical `osm` or `mga` blueprint)
    - deploy: bundles — a blueprint pinned with your configuration,
      ready to run
    - execute: instances — run the bundle, launching agent instances that
      process your data and produce results
    """

    blueprints: BlueprintsApi
    bundles: BundlesApi
    instances: InstancesApi

    def __init__(self, api_key: str, api_endpoint: str, agent_endpoint: str = "") -> None:
        # The agent API has its own endpoint; by default it is served from the
        # root of the main endpoint, without the version path.
        agent_endpoint = agent_endpoint or _default_agent_endpoint(api_endpoint)
        super().__init__(api_key, agent_endpoint)
        self.blueprints = BlueprintsApi(api_key, agent_endpoint)
        self.bundles = BundlesApi(api_key, agent_endpoint)
        self.instances = InstancesApi(api_key, agent_endpoint)

    def get_node_registry(self) -> dict:
        """Gets the registry of connector and processing nodes available to blueprints."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/nodes/registry")
        return self.requests_get(api_endpoint)
