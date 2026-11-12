from __future__ import annotations

import gzip
import shutil
import uuid
from pathlib import Path

import pytest

from archetypeai import ApiError, ArchetypeAI, pformat

from agents_test import EXAMPLE_DATA_DIR, copy_into, require

OSM_BLUEPRINT_KEY = "osm"
OSM_LARCO_DIR = EXAMPLE_DATA_DIR / "osm_larco"
AD_BLUEPRINT_KEY = "ad"
AD_TEP_DIR = EXAMPLE_DATA_DIR / "ad_tep"
RED_BLUEPRINT_KEY = "red"
RED_PUMP_DIR = EXAMPLE_DATA_DIR / "red_pump"
STATES = ["fill", "wash", "spin", "drain"]
DATA_COLUMNS = [f"{sensor}.{axis}" for sensor in ("back", "side", "top") for axis in ("x", "y", "z")]
OVERRIDES = {"values": {"states": STATES, "timestamp_column": "timestamp", "data_columns": DATA_COLUMNS}}
TERMINAL_STATUSES = ("completed", "failed", "cancelled")

# Generous ceiling for each platform step; a single-trial optimization of the
# sample data usually finishes in a few minutes.
MAX_STEP_TIME_SEC = 1800.0


def upload(
    client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str], name: str, data_dir: Path = OSM_LARCO_DIR
) -> str:
    """Unpacks a gzipped example CSV (`<role>/<file>.csv`), uploads it under a unique name and returns its file ID."""
    stem = Path(name).name.removesuffix(".csv")
    path = tmp_path / f"{stem}_{uuid.uuid4().hex[:8]}.csv"
    with gzip.open(data_dir / f"{name}.gz", "rb") as packed, path.open("wb") as out:
        shutil.copyfileobj(packed, out)
    file_id = require(client.files.local.upload(str(path)), "file_id")
    uploaded_files.append(file_id)
    return file_id


def training_examples(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]) -> list[dict]:
    """One training example per state, each labeled by a constant."""
    return [
        {
            "inputs": [
                {
                    "type": "file",
                    "id": upload(client, tmp_path, uploaded_files, f"library/{state}__osm_larco_library.csv"),
                }
            ],
            "ground_truth": {"state": {"from": {"constant": state}}},
        }
        for state in STATES
    ]


def labeled_example(file_id: str) -> dict:
    """An example scored against the labels in its `label` column."""
    return {"inputs": [{"type": "file", "id": file_id}], "ground_truth": {"state": {"from": {"column": "label"}}}}


def single_trial_search_space(k_neighbors: int) -> dict:
    """A one-point search space, so the run spends exactly one trial."""
    values = {
        "window_size": 512,
        "step_size": 512,
        "k_neighbors": k_neighbors,
        "metric": "cosine",
        "weights": "uniform",
    }
    return {
        "parameters": {
            name: {"kind": "value", "spec": {"type": "categorical", "values": [value]}}
            for name, value in values.items()
        }
    }


def test_optimization_create_list_cancel_delete(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    """Create an optimization, find it, cancel it and delete it, without waiting for its trials."""
    blueprint_id = require(client.agents.blueprints.get(OSM_BLUEPRINT_KEY), "id")
    created = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="macro_f1",
        training_examples=training_examples(client, tmp_path, uploaded_files),
        validation_examples=[
            labeled_example(upload(client, tmp_path, uploaded_files, "validation/osm_larco_validation.csv"))
        ],
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


def cancel_quietly(api, resource_id: str) -> None:
    """Cancels a resource and waits for it to stop. A 409 means it already finished on its own."""
    try:
        api.cancel(resource_id)
    except ApiError:
        return
    api.wait_until_done(resource_id, timeout_sec=300.0)


def delete_lifecycle(
    client: ArchetypeAI,
    optimization_id: str,
    promoted_id: str | None,
    eval_id: str | None,
    package_id: str | None,
    deployment_id: str | None,
    session_id: str | None,
) -> None:
    """Deletes what a lifecycle test created, whichever step it stopped at.

    Each resource is cancelled or stopped before it is deleted, since only an ended one
    can be deleted. A deployment cannot be deleted while it has sessions, a package while
    it has deployments, and the promoted blueprint while a package or an eval holds it.
    """
    if session_id:
        cancel_quietly(client.agents.sessions, session_id)
        client.agents.sessions.delete(session_id)
    if deployment_id:
        try:
            client.agents.deployments.stop(deployment_id)
        except ApiError:
            # 409: the deployment already ended.
            pass
        client.agents.deployments.wait_until_ready(deployment_id, timeout_sec=300.0)
        client.agents.deployments.delete(deployment_id)
    if package_id:
        client.agents.packages.delete(package_id)
    if eval_id:
        cancel_quietly(client.agents.evals, eval_id)
        client.agents.evals.delete(eval_id)
    if promoted_id:
        client.agents.blueprints.delete(promoted_id)
    cancel_quietly(client.agents.optimizations, optimization_id)
    client.agents.optimizations.delete(optimization_id)


def test_osm_lifecycle_end_to_end(client: ArchetypeAI, project: str, tmp_path: Path, uploaded_files: list[str]):
    """Optimize the OSM blueprint, promote its trial, eval it on held-out data, then package and run it."""
    blueprint_id = copy_into(client, project, OSM_BLUEPRINT_KEY)
    optimization = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="macro_f1",
        training_examples=training_examples(client, tmp_path, uploaded_files),
        validation_examples=[
            labeled_example(upload(client, tmp_path, uploaded_files, "validation/osm_larco_validation.csv"))
        ],
        max_trials=1,
        search_space=single_trial_search_space(5),
        overrides=OVERRIDES,
        name=f"python_client_test_{uuid.uuid4().hex[:8]}",
    )
    optimization_id = require(optimization, "id")
    promoted_id = eval_id = package_id = deployment_id = session_id = None
    try:
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
        evaluation = client.agents.evals.wait_until_done(eval_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert evaluation.get("status") == "completed", pformat(evaluation)
        primary = (evaluation.get("metrics_report") or {}).get("primary") or {}
        assert isinstance(primary.get("value"), float), pformat(evaluation)
        examples = client.agents.evals.list_examples(eval_id).get("data", [])
        assert [example.get("status") for example in examples] == ["completed"], pformat(examples)

        package_id = require(client.agents.packages.create(promoted_id, name="python_client_test"), "id")
        package = client.agents.packages.wait_until_ready(package_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert package.get("status") == "ready", pformat(package)
        delivery_id = upload(client, tmp_path, uploaded_files, "delivery/osm_larco_delivery.csv")
        deployment_id = require(client.agents.deployments.create(package_id, kind="batch"), "id")
        deployment = client.agents.deployments.wait_until_ready(deployment_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert deployment.get("status") == "ready", pformat(deployment)
        session_id = require(client.agents.sessions.create(deployment_id, source=[delivery_id]), "id")
        session = client.agents.sessions.wait_until_done(session_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert session.get("status") == "completed", pformat(client.agents.sessions.get_events(session_id))
        results = client.agents.sessions.get_results(session_id)
        assert results.get("data"), f"Completed session returned no results: {pformat(results)}"
    finally:
        delete_lifecycle(client, optimization_id, promoted_id, eval_id, package_id, deployment_id, session_id)


def ad_example(file_id: str, ground_truth: dict) -> dict:
    """An AD example whose windows each take the label of their last row."""
    return {
        "inputs": [{"type": "file", "id": file_id}],
        "ground_truth": {"anomaly": {**ground_truth, "downsampling": "last_record"}},
    }


def test_ad_lifecycle_end_to_end(client: ArchetypeAI, project: str, tmp_path: Path, uploaded_files: list[str]):
    """Optimize the AD blueprint, promote its trial, eval it on held-out data, then package and run it."""

    def upload_ad(name: str) -> str:
        return upload(client, tmp_path, uploaded_files, name, data_dir=AD_TEP_DIR)

    library = sorted(path.name.removesuffix(".gz") for path in (AD_TEP_DIR / "library").glob("*.csv.gz"))
    with gzip.open(AD_TEP_DIR / "validation" / "ad_tep_validation.csv.gz", "rt") as f:
        columns = f.readline().strip().split(",")
    blueprint_id = copy_into(client, project, AD_BLUEPRINT_KEY)
    optimization = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="macro_f1",
        training_examples=[
            ad_example(upload_ad(f"library/{name}"), {"from": {"constant": "normal"}}) for name in library
        ],
        validation_examples=[ad_example(upload_ad("validation/ad_tep_validation.csv"), {"from": {"column": "label"}})],
        max_trials=1,
        # The search space cannot be empty, so it holds a single point.
        search_space={"parameters": {"n_neighbors": {"kind": "value", "spec": {"type": "categorical", "values": [5]}}}},
        overrides={
            "values": {
                "timestamp_column": columns[0],
                "data_columns": [c for c in columns[1:] if c != "label"],
                "window_size": 48,
                "step_size": 8,
                "feature_names": ["std", "range", "slope", "median"],
                "metric": "l2",
                "pca_components": 16,
                "threshold": 1.215,
            }
        },
        name=f"python_client_test_{uuid.uuid4().hex[:8]}",
    )
    optimization_id = require(optimization, "id")
    promoted_id = eval_id = package_id = deployment_id = session_id = None
    try:
        optimization = client.agents.optimizations.wait_until_done(optimization_id, timeout_sec=MAX_STEP_TIME_SEC)
        trials = client.agents.optimizations.list_trials(optimization_id).get("data", [])
        best_trial = optimization.get("best_trial")
        if optimization.get("status") != "completed" or not best_trial:
            pytest.fail(f"Optimization {optimization_id} has no winning trial: {pformat(trials)}")
        assert best_trial.get("objective_value") is not None, pformat(best_trial)

        promoted = client.agents.optimizations.promote_trial(optimization_id, require(best_trial, "id"))
        promoted_id = require(promoted, "id")

        test_file_id = upload_ad("test/ad_tep_test.csv")
        evaluation = client.agents.evals.create(
            promoted_id, examples=[ad_example(test_file_id, {"from": {"column": "label"}})]
        )
        eval_id = require(evaluation, "id")
        evaluation = client.agents.evals.wait_until_done(eval_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert evaluation.get("status") == "completed", pformat(evaluation)
        primary = (evaluation.get("metrics_report") or {}).get("primary") or {}
        assert primary.get("target") == "anomaly", pformat(evaluation)
        assert isinstance(primary.get("value"), float), pformat(evaluation)

        package_id = require(client.agents.packages.create(promoted_id, name="python_client_test"), "id")
        package = client.agents.packages.wait_until_ready(package_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert package.get("status") == "ready", pformat(package)
        delivery_id = upload_ad("delivery/ad_tep_delivery.csv")
        deployment_id = require(client.agents.deployments.create(package_id, kind="batch"), "id")
        deployment = client.agents.deployments.wait_until_ready(deployment_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert deployment.get("status") == "ready", pformat(deployment)
        session_id = require(client.agents.sessions.create(deployment_id, source=[delivery_id]), "id")
        session = client.agents.sessions.wait_until_done(session_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert session.get("status") == "completed", pformat(client.agents.sessions.get_events(session_id))
        results = client.agents.sessions.get_results(session_id)
        assert results.get("data"), f"Completed session returned no results: {pformat(results)}"
    finally:
        delete_lifecycle(client, optimization_id, promoted_id, eval_id, package_id, deployment_id, session_id)


def red_example(file_id: str, ground_truth: dict) -> dict:
    """A RED example whose windows each take the label of their last row."""
    return {
        "inputs": [{"type": "file", "id": file_id}],
        "ground_truth": {"event": {**ground_truth, "downsampling": "last_record"}},
    }


def test_red_lifecycle_end_to_end(client: ArchetypeAI, project: str, tmp_path: Path, uploaded_files: list[str]):
    """Optimize the RED blueprint, promote its trial, eval it on held-out data, then package and run it."""

    def upload_red(name: str) -> str:
        return upload(client, tmp_path, uploaded_files, name, data_dir=RED_PUMP_DIR)

    library = sorted(path.name.removesuffix(".gz") for path in (RED_PUMP_DIR / "library").glob("*.csv.gz"))
    with gzip.open(RED_PUMP_DIR / "validation" / "red_pump_validation.csv.gz", "rt") as f:
        columns = f.readline().strip().split(",")
    blueprint_id = copy_into(client, project, RED_BLUEPRINT_KEY)
    optimization = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="foreground_macro_f1",
        training_examples=[
            red_example(upload_red(f"library/{name}"), {"from": {"constant": name.split("__")[0]}}) for name in library
        ],
        validation_examples=[
            red_example(upload_red("validation/red_pump_validation.csv"), {"from": {"column": "label"}})
        ],
        max_trials=1,
        # The search space cannot be empty, so it holds a single point.
        search_space={"parameters": {"metric": {"kind": "value", "spec": {"type": "categorical", "values": ["l1"]}}}},
        overrides={
            "values": {
                "events": ["normal", "pump_breakdown"],
                "background": "normal",
                "timestamp_column": columns[0],
                "data_columns": [c for c in columns[1:] if c != "label"],
                "window_size": 64,
                "step_size": 1,
            }
        },
        name=f"python_client_test_{uuid.uuid4().hex[:8]}",
    )
    optimization_id = require(optimization, "id")
    promoted_id = eval_id = package_id = deployment_id = session_id = None
    try:
        optimization = client.agents.optimizations.wait_until_done(optimization_id, timeout_sec=MAX_STEP_TIME_SEC)
        trials = client.agents.optimizations.list_trials(optimization_id).get("data", [])
        best_trial = optimization.get("best_trial")
        if optimization.get("status") != "completed" or not best_trial:
            pytest.fail(f"Optimization {optimization_id} has no winning trial: {pformat(trials)}")
        assert best_trial.get("objective_value") is not None, pformat(best_trial)

        promoted = client.agents.optimizations.promote_trial(optimization_id, require(best_trial, "id"))
        promoted_id = require(promoted, "id")

        test_file_id = upload_red("test/red_pump_test.csv")
        evaluation = client.agents.evals.create(
            promoted_id, examples=[red_example(test_file_id, {"from": {"column": "label"}})]
        )
        eval_id = require(evaluation, "id")
        evaluation = client.agents.evals.wait_until_done(eval_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert evaluation.get("status") == "completed", pformat(evaluation)
        primary = (evaluation.get("metrics_report") or {}).get("primary") or {}
        assert primary.get("target") == "event", pformat(evaluation)
        assert isinstance(primary.get("value"), float), pformat(evaluation)

        package_id = require(client.agents.packages.create(promoted_id, name="python_client_test"), "id")
        package = client.agents.packages.wait_until_ready(package_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert package.get("status") == "ready", pformat(package)
        delivery_id = upload_red("delivery/red_pump_delivery.csv")
        deployment_id = require(client.agents.deployments.create(package_id, kind="batch"), "id")
        deployment = client.agents.deployments.wait_until_ready(deployment_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert deployment.get("status") == "ready", pformat(deployment)
        session_id = require(client.agents.sessions.create(deployment_id, source=[delivery_id]), "id")
        session = client.agents.sessions.wait_until_done(session_id, timeout_sec=MAX_STEP_TIME_SEC)
        assert session.get("status") == "completed", pformat(client.agents.sessions.get_events(session_id))
        results = client.agents.sessions.get_results(session_id)
        assert results.get("data"), f"Completed session returned no results: {pformat(results)}"
    finally:
        delete_lifecycle(client, optimization_id, promoted_id, eval_id, package_id, deployment_id, session_id)
