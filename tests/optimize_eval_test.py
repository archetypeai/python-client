from __future__ import annotations

import gzip
import shutil
import uuid
from pathlib import Path

import pytest

from archetypeai import ApiError, ArchetypeAI, pformat

from agents_test import EXAMPLE_DATA_DIR, require

OSM_BLUEPRINT_KEY = "osm"
OSM_LARCO_DIR = EXAMPLE_DATA_DIR / "osm_larco"
STATES = ["fill", "wash", "spin", "drain"]
DATA_COLUMNS = [f"{sensor}.{axis}" for sensor in ("back", "side", "top") for axis in ("x", "y", "z")]
OVERRIDES = {"values": {"states": STATES, "timestamp_column": "timestamp", "data_columns": DATA_COLUMNS}}
TERMINAL_STATUSES = ("completed", "failed", "cancelled")

# Generous ceiling for each platform step; a single-trial optimization of the
# sample data usually finishes in a few minutes.
MAX_STEP_TIME_SEC = 1800.0


def upload(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str], name: str) -> str:
    """Unpacks a gzipped example CSV (`<role>/<file>.csv`), uploads it under a unique name and returns its file ID."""
    stem = Path(name).name.removesuffix(".csv")
    path = tmp_path / f"{stem}_{uuid.uuid4().hex[:8]}.csv"
    with gzip.open(OSM_LARCO_DIR / f"{name}.gz", "rb") as packed, path.open("wb") as out:
        shutil.copyfileobj(packed, out)
    file_id = require(client.files.local.upload(str(path)), "file_id")
    uploaded_files.append(file_id)
    return file_id


def training_examples(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]) -> list[dict]:
    """One training example per state, each labeled by a constant."""
    return [
        {
            "inputs": [{"type": "file", "id": upload(client, tmp_path, uploaded_files, f"library/{state}__osm_larco_library.csv")}],
            "ground_truth": {"state": {"from": {"constant": state}}},
        }
        for state in STATES
    ]


def labeled_example(file_id: str) -> dict:
    """An example scored against the labels in its `label` column."""
    return {"inputs": [{"type": "file", "id": file_id}], "ground_truth": {"state": {"from": {"column": "label"}}}}


def single_trial_search_space(k_neighbors: int) -> dict:
    """A one-point search space, so the run spends exactly one trial."""
    values = {"window_size": 512, "step_size": 512, "k_neighbors": k_neighbors, "metric": "cosine", "weights": "uniform"}
    return {
        "parameters": {
            name: {"kind": "value", "spec": {"type": "categorical", "values": [value]}} for name, value in values.items()
        }
    }


def test_optimization_create_list_cancel_delete(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    """Create an optimization, find it, cancel it and delete it, without waiting for its trials."""
    blueprint_id = require(client.agents.blueprints.get(OSM_BLUEPRINT_KEY), "id")
    created = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="macro_f1",
        training_examples=training_examples(client, tmp_path, uploaded_files),
        validation_examples=[labeled_example(upload(client, tmp_path, uploaded_files, "validation/osm_larco_validation.csv"))],
        max_trials=1,
        search_space=single_trial_search_space(5),
        overrides=OVERRIDES,
        name=f"python_client_test_{uuid.uuid4().hex[:8]}",
    )
    optimization_id = require(created, "id")
    try:
        optimization = client.agents.optimizations.get(optimization_id)
        assert optimization.get("blueprint_id") == blueprint_id, pformat(optimization)

        listed = client.agents.optimizations.list(blueprint_id=blueprint_id, limit=100).get("data", [])
        assert optimization_id in [item.get("id") for item in listed], pformat(listed)
        assert "data" in client.agents.optimizations.list_trials(optimization_id)

        try:
            client.agents.optimizations.cancel(optimization_id)
        except ApiError:
            # 409: the run already reached a terminal status on its own.
            pass
        optimization = client.agents.optimizations.wait_until_done(optimization_id, timeout_sec=300.0)
        assert optimization.get("status") in TERMINAL_STATUSES, pformat(optimization)
    finally:
        client.agents.optimizations.delete(optimization_id)
    with pytest.raises(ApiError):
        client.agents.optimizations.get(optimization_id)


def test_osm_lifecycle_end_to_end(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    """Optimize the OSM blueprint, promote its trial, eval it on held-out data, then bundle and run it."""
    blueprint_id = require(client.agents.blueprints.get(OSM_BLUEPRINT_KEY), "id")
    optimization = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="macro_f1",
        training_examples=training_examples(client, tmp_path, uploaded_files),
        validation_examples=[labeled_example(upload(client, tmp_path, uploaded_files, "validation/osm_larco_validation.csv"))],
        max_trials=1,
        search_space=single_trial_search_space(5),
        overrides=OVERRIDES,
        name=f"python_client_test_{uuid.uuid4().hex[:8]}",
    )
    optimization_id = require(optimization, "id")
    optimization = client.agents.optimizations.wait_until_done(optimization_id, timeout_sec=MAX_STEP_TIME_SEC)
    trials = client.agents.optimizations.list_trials(optimization_id).get("data", [])
    best_trial = optimization.get("best_trial")
    if optimization.get("status") != "completed" or not best_trial:
        pytest.fail(f"Optimization {optimization_id} has no winning trial: {pformat(trials)}")
    assert best_trial.get("objective_value") is not None, pformat(best_trial)

    promoted = client.agents.optimizations.promote_trial(optimization_id, require(best_trial, "id"))
    promoted_id = require(promoted, "id")

    test_file_id = upload(client, tmp_path, uploaded_files, "test/osm_larco_test.csv")
    evaluation = client.agents.evals.create(promoted_id, examples=[labeled_example(test_file_id)])
    eval_id = require(evaluation, "id")
    try:
        evaluation = client.agents.evals.wait_until_done(eval_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert evaluation.get("status") == "completed", pformat(evaluation)
        primary = (evaluation.get("metrics_report") or {}).get("primary") or {}
        assert isinstance(primary.get("value"), float), pformat(evaluation)
        examples = client.agents.evals.list_examples(eval_id).get("data", [])
        assert [example.get("status") for example in examples] == ["completed"], pformat(examples)
    finally:
        client.agents.evals.delete(eval_id)

    bundle_id = require(client.agents.bundles.create(blueprint=promoted_id, name="python_client_test"), "id")
    agent_id = None
    try:
        delivery_id = upload(client, tmp_path, uploaded_files, "delivery/osm_larco_delivery.csv")
        agent_id = require(client.agents.bundles.run(bundle_id, source=[delivery_id]), "id")
        agent = client.agents.instances.wait_until_done(agent_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert agent.get("status") == "completed", pformat(client.agents.instances.get_events(agent_id))
        results = client.agents.instances.get_results(agent_id)
        assert results.get("data"), f"Completed agent returned no results: {pformat(results)}"
    finally:
        # A bundle cannot be deleted while an agent run still references it.
        if agent_id:
            client.agents.instances.delete(agent_id)
        client.agents.bundles.delete(bundle_id)
        client.agents.optimizations.delete(optimization_id)
