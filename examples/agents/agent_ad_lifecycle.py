# An example that takes an AD (Anomaly Discovery) agent through its full lifecycle
# on your own data, in four phases: develop, build, deploy and run.
#
#   Develop: upload the training, validation, test and delivery files. Copy the
#     canonical `ad` blueprint into a project and optimize it: each trial fits an
#     anomaly detector on the training files, which hold normal data only, and is
#     scored on the labeled validation files. Promote the best trial to a blueprint
#     of your own, then eval that blueprint once on the held-out test files.
#   Build: package the promoted blueprint for the platform.
#   Deploy: deploy the package as batch, and later as serving.
#   Run: on the batch deployment, run a session on the delivery files, whose labels
#     are unknown. On the serving deployment, open a session and query it with the
#     first rows of a delivery file, sent inline.
#
# --data_dir holds one folder per role, each with CSV files (plain or gzipped,
# gzipped ones are unpacked before upload):
# - library/*.csv: training data, normal operation only, no label column;
# - validation/*.csv and test/*.csv: labeled `normal` or `anomaly` by a `label` column;
# - delivery/*.csv: the data to run the deployed agent on, without labels.
# Every file shares the same columns: the timestamp first, then the sensor channels.
# A window takes the label of its last row.
#
# Default input is example_data/ad_tep/: 33 process variables of the Tennessee Eastman
# chemical process, sampled every 3 minutes, with six kinds of process fault (public
# domain, see example_data/ad_tep/README.md).
#
# The detector flags a window when its anomaly score is over `threshold`: lower flags
# more windows, higher raises fewer false alarms.
# usage:
#   python -m examples.agents.agent_ad_lifecycle --api_key=<YOUR_API_KEY>
#   python -m examples.agents.agent_ad_lifecycle --api_key=<YOUR_API_KEY> --data_dir=<your roles>
import glob
import gzip
import logging
import os
import shutil
import tempfile

from archetypeai import ArchetypeAI, ArgParser, pformat

from examples.agents.common import (
    build_package,
    get_or_copy_blueprint,
    get_or_create_project,
    read_channels,
    require,
    run_batch_and_serving,
)

# The canonical blueprint every optimization starts from.
AD_BLUEPRINT_KEY = "ad"
# The column validation and test files carry their labels in.
LABEL_COLUMN = "label"
# The per-channel features the detector reads off each window.
FEATURE_NAMES = ["std", "range", "slope", "median"]


def role_files(data_dir: str, role: str) -> list[str]:
    """The CSV files of one role, plain or gzipped, sorted by name."""
    folder = os.path.join(data_dir, role)
    files = sorted(glob.glob(os.path.join(folder, "*.csv")) + glob.glob(os.path.join(folder, "*.csv.gz")))
    assert files, f"No CSV files in {folder}"
    return files


def read_header(path: str) -> list[str]:
    """The column names of a plain or gzipped CSV file."""
    with gzip.open(path, "rt") if path.endswith(".gz") else open(path) as f:
        return f.readline().strip().split(",")


def example(file_id: str, ground_truth: dict) -> dict:
    """An example whose windows each take the label of their last row."""
    return {
        "inputs": [{"type": "file", "id": file_id}],
        "ground_truth": {"anomaly": {**ground_truth, "downsampling": "last_record"}},
    }


def categorical(values: list) -> dict:
    """A search space entry trying each of values for a blueprint value."""
    return {"kind": "value", "spec": {"type": "categorical", "values": values}}


def log_anomaly_report(prefix: str, metrics_report: dict) -> None:
    """Logs macro F1, anomaly recall and precision, and the false-alarm rate of a metrics report.

    The figures are the report's own. A window the agent made no prediction for (an
    invalid window) counts as a miss of its true class.
    """
    target = (metrics_report or {}).get("targets", {}).get("anomaly", {})
    names, per_class = target.get("class_names"), target.get("per_class")
    if not names or not per_class:
        logging.info(f"{prefix}: {pformat(metrics_report)}")
        return
    a, n = names.index("anomaly"), names.index("normal")
    support = per_class["support"]
    # Rows are the true class, columns the predicted class.
    false_alarms = target["confusion_matrix"][n][a]
    unpredicted = sum(target.get("missed") or [])
    logging.info(
        f"{prefix}: macro_f1={target.get('aggregate', {}).get('macro_f1')} "
        f"recall={per_class['recall'][a]:.3f} precision={per_class['precision'][a]:.3f} "
        f"false_alarm_rate={false_alarms / max(support[n], 1):.3%} "
        f"({sum(support)} windows, {unpredicted} with no prediction)"
    )


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # The input columns are read off a labeled file.
    columns = read_header(role_files(args.data_dir, "validation")[0])
    timestamp_column, data_columns = columns[0], [c for c in columns[1:] if c != LABEL_COLUMN]
    logging.info(f"Data columns: {data_columns}")

    # Develop: upload the data. Files are always uploaded, replacing any file of the same name,
    # so the run never scores a stale copy. The platform reads plain CSV, so a gzipped
    # file is unpacked to a scratch directory first.
    with tempfile.TemporaryDirectory() as scratch_dir:

        def upload(path: str) -> str:
            if path.endswith(".gz"):
                unpacked = os.path.join(scratch_dir, os.path.basename(path)[: -len(".gz")])
                with gzip.open(path, "rb") as packed, open(unpacked, "wb") as out:
                    shutil.copyfileobj(packed, out)
                path = unpacked
            file_id = require(client.files.local.upload(path), "file_id")
            logging.info(f"Uploaded input file: {file_id}")
            return file_id

        library_ids = [upload(path) for path in role_files(args.data_dir, "library")]
        validation_ids = [upload(path) for path in role_files(args.data_dir, "validation")]
        test_ids = [upload(path) for path in role_files(args.data_dir, "test")]
        delivery_ids = [upload(path) for path in role_files(args.data_dir, "delivery")]

    # Training files hold normal data only, so their label is a constant. Validation
    # and test files are scored against their label column.
    training_examples = [example(file_id, {"from": {"constant": "normal"}}) for file_id in library_ids]
    validation_examples = [example(file_id, {"from": {"column": LABEL_COLUMN}}) for file_id in validation_ids]

    # Optimize the canonical blueprint. The overrides apply to every trial and carry
    # over to the promoted blueprint: the input columns, the windowing, the features
    # and the threshold (required by `ad`). Size the window to your sampling rate:
    # 48 samples is 2.4 hours of TEP data. The search space is what the trials vary.
    # Copy the canonical blueprint into the examples project: everything derived from it,
    # the optimization, the promoted blueprint and its package, is then in that project,
    # where the package can be deployed.
    project_id = get_or_create_project(client)
    blueprint_id = get_or_copy_blueprint(client, project_id, AD_BLUEPRINT_KEY, f"{AD_BLUEPRINT_KEY}-lifecycle-example")
    optimization = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="macro_f1",
        training_examples=training_examples,
        validation_examples=validation_examples,
        max_trials=len(args.n_neighbors),
        search_space={"parameters": {"n_neighbors": categorical(args.n_neighbors)}},
        overrides={
            "values": {
                "timestamp_column": timestamp_column,
                "data_columns": data_columns,
                "window_size": args.window_size,
                "step_size": args.step_size,
                "feature_names": FEATURE_NAMES,
                "metric": "l2",
                "pca_components": 16,
                "threshold": args.threshold,
            }
        },
        name="AD lifecycle example",
    )
    optimization_id = require(optimization, "id")
    logging.info(f"Started optimization_id: {optimization_id}")

    # Wait for every trial to finish, then rank them by their validation score.
    optimization = client.agents.optimizations.wait_until_done(optimization_id, timeout_sec=args.max_run_time_sec)
    logging.info(f"Optimization finished with status: {optimization.get('status')}")
    trials = client.agents.optimizations.list_trials(optimization_id).get("data", [])
    for trial in sorted(trials, key=lambda t: t.get("objective_value") or -1.0, reverse=True):
        log_anomaly_report(
            f"  trial #{trial.get('trial_number')} {trial.get('status')} values={trial.get('trial_values')}",
            trial.get("metrics_report"),
        )
        if trial.get("error"):
            logging.error(f"  trial #{trial.get('trial_number')} error: {trial['error']}")
    best_trial = optimization.get("best_trial")
    if optimization.get("status") != "completed" or not best_trial:
        logging.error(f"Optimization has no winning trial: {pformat(optimization)}")
        return

    # Promote the winner: a blueprint of your own, with the fitted detector attached.
    blueprint = client.agents.optimizations.promote_trial(optimization_id, require(best_trial, "id"))
    promoted_id = require(blueprint, "id")
    logging.info(f"Promoted trial #{best_trial.get('trial_number')} to blueprint {blueprint.get('blueprint_key')}")

    # Eval the promoted blueprint once on the held-out test files.
    evaluation = client.agents.evals.create(
        promoted_id,
        examples=[example(file_id, {"from": {"column": LABEL_COLUMN}}) for file_id in test_ids],
        name="AD lifecycle example: test",
    )
    evaluation = client.agents.evals.wait_until_done(require(evaluation, "id"), timeout_sec=args.max_run_time_sec)
    if evaluation.get("status") != "completed":
        logging.error(f"Eval did not complete: {pformat(evaluation)}")
        return
    log_anomaly_report("Test score", evaluation.get("metrics_report"))

    # Build: package the promoted blueprint, its fitted model resolved once.
    # Deploy and run: deploy the package as batch and run a session on the unlabeled
    # delivery files, one output per file. Then deploy it as serving, and query it with
    # the first delivery file, --rows_per_query rows at a time. The promoted blueprint
    # is kept.
    package_id = build_package(client, promoted_id, name="AD lifecycle example")
    run_batch_and_serving(
        client,
        package_id,
        delivery_ids,
        read_channels(role_files(args.data_dir, "delivery")[0]),
        args.rows_per_query,
        args.num_queries,
        args.max_run_time_sec,
    )


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--data_dir", default="example_data/ad_tep", type=str)
    parser.add_argument("--n_neighbors", default=[5, 10], type=int, nargs="+", help="One trial per value")
    parser.add_argument("--window_size", default=48, type=int, help="Samples per window")
    parser.add_argument("--step_size", default=8, type=int, help="Samples between window starts")
    parser.add_argument("--threshold", default=1.215, type=float, help="Anomaly score that flags a window")
    parser.add_argument("--rows_per_query", default=96, type=int, help="Delivery rows sent in each serving query")
    parser.add_argument("--num_queries", default=3, type=int, help="Serving queries to send")
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float, help="Per step; negative waits forever")
    args = parser.parse_args(configure_logging=True)

    main(args)
