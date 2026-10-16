from __future__ import annotations

import json
import logging
import time

from archetypeai._base import ApiBase
from archetypeai._errors import ApiError

# Statuses where an agent has finished and will not change state again.
TERMINAL_AGENT_STATUSES = ("completed", "failed", "cancelled")


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


def _as_example(example: str | dict) -> dict:
    """Converts a plain file ID into an eval example, passing dicts through untouched."""
    if isinstance(example, str):
        return {"inputs": [_as_data_ref(example)]}
    return example


def _wait_until_terminal(
    get_resource,
    resource_id: str,
    kind: str,
    poll_interval_sec: float,
    timeout_sec: float,
    describe=None,
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
        if status in TERMINAL_AGENT_STATUSES:
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
        models: dict | None = None,
        values: dict | None = None,
        artifacts: dict | None = None,
    ) -> dict:
        """Creates a bundle pinned to a blueprint and returns its metadata.

        Pass blueprint as a `blp_` id or key (e.g. `mga`). Bundles are created
        ready to run and are owned by your org. models is a per-slot model
        override, e.g. {"vision": "omega-1.5"}; omit to use the blueprint's
        default model for every slot.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/bundles")
        payload: dict = {
            "blueprint": blueprint,
            "name": name,
            "description": description,
        }
        if models is not None:
            payload["models"] = models
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
        return _wait_until_terminal(self.get, agent_id, "agent", poll_interval_sec, timeout_sec)


class EvalsApi(_AgentApiBase):
    """Main class for handling all eval API calls.

    An eval scores a blueprint on labeled examples and reports its metrics, e.g.
    the macro F1 of an OSM blueprint's predicted states.
    """

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        before: str | None = None,
        status: str | None = None,
        query: str | None = None,
        blueprint_id: str | None = None,
    ) -> dict:
        """Lists the evals in your org, newest first.

        Pass the previous page's next_cursor as after to fetch the next page. Pass
        status (e.g. `running`), query (substring match), or blueprint_id to filter.
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
    ) -> dict:
        """Creates and starts an eval of a blueprint, and returns its metadata.

        Pass blueprint_id as a `blp_` ID. Each example is either a file ID or an
        example dict, e.g. {"inputs": [{"type": "file", "id": "file_abc123"}],
        "ground_truth": {...}}. A file ID alone works when the file carries its
        labels in a column named after the target, e.g. `state` for OSM.
        primary (e.g. `state.macro_f1`) and targets override the blueprint's
        scoring defaults for this run.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/evals")
        payload: dict = {
            "blueprint_id": blueprint_id,
            "examples": [_as_example(example) for example in examples],
            "name": name,
        }
        payload.update(_drop_missing({"primary": primary, "targets": targets, "emit_predictions": emit_predictions}))
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
    the winning trial to get a blueprint of your own, ready to bundle and run.
    """

    def list(
        self,
        limit: int | None = None,
        after: str | None = None,
        before: str | None = None,
        status: str | None = None,
        query: str | None = None,
        blueprint_id: str | None = None,
    ) -> dict:
        """Lists the optimizations in your org, newest first.

        Pass the previous page's next_cursor as after to fetch the next page. Pass
        status (e.g. `running`), query (substring match), or blueprint_id to filter.
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
        objective: str,
        validation_examples: list[str | dict],
        max_trials: int,
        training_examples: list[str | dict] | None = None,
        calibration_examples: list[str | dict] | None = None,
        search_space: dict | None = None,
        overrides: dict | None = None,
        constraints: dict | None = None,
        name: str = "",
    ) -> dict:
        """Creates and starts an optimization of a blueprint, and returns its metadata.

        Pass blueprint_id as a `blp_` ID and objective as one of the blueprint's
        metrics, e.g. `macro_f1`. Examples take the same form as for evals. The
        run spends at most max_trials trials sampling search_space, e.g.
        {"parameters": {"k_neighbors": {"kind": "value", "spec": {"type":
        "categorical", "values": [5, 31]}}}}. overrides sets blueprint values or
        models for every trial, e.g. {"values": {"states": ["idle", "running"]}};
        values the blueprint marks as required must be set here.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/optimizations")
        payload: dict = {
            "blueprint_id": blueprint_id,
            "objective": objective,
            "validation_examples": [_as_example(example) for example in validation_examples],
            "budget": {"max_trials": max_trials},
            "name": name,
        }
        if training_examples is not None:
            payload["training_examples"] = [_as_example(example) for example in training_examples]
        if calibration_examples is not None:
            payload["calibration_examples"] = [_as_example(example) for example in calibration_examples]
        payload.update(_drop_missing({"search_space": search_space, "overrides": overrides, "constraints": constraints}))
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

    def wait_until_done(
        self, optimization_id: str, poll_interval_sec: float = 30.0, timeout_sec: float = -1.0
    ) -> dict:
        """Polls an optimization until it reaches a terminal status and returns its metadata.

        Logs trial progress while it runs. Raises a TimeoutError if the run is still
        going after timeout_sec seconds (a negative timeout, the default, waits forever).
        """
        return _wait_until_terminal(
            self.get, optimization_id, "optimization", poll_interval_sec, timeout_sec, _describe_progress
        )


class AgentsApi(ApiBase):
    """Main class for handling all agent API calls.

    The agent platform follows a develop -> deploy -> execute lifecycle:
    - develop: blueprints — the reusable agent definition
      (e.g. the canonical `osm` or `mga` blueprint)
    - deploy: bundles — a blueprint pinned with your configuration,
      ready to run
    - execute: instances — run the bundle, launching agent instances that
      process your data and produce results

    Evals score a blueprint on labeled data; optimizations search a blueprint's
    values and fit its models, and promote the best trial to a new blueprint.
    """

    blueprints: BlueprintsApi
    bundles: BundlesApi
    instances: InstancesApi
    evals: EvalsApi
    optimizations: OptimizationsApi

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)
        self.blueprints = BlueprintsApi(api_key, api_endpoint)
        self.bundles = BundlesApi(api_key, api_endpoint)
        self.instances = InstancesApi(api_key, api_endpoint)
        self.evals = EvalsApi(api_key, api_endpoint)
        self.optimizations = OptimizationsApi(api_key, api_endpoint)

    def get_node_registry(self) -> dict:
        """Gets the registry of connector and processing nodes available to blueprints."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "agents/nodes/registry")
        return self.requests_get(api_endpoint)
