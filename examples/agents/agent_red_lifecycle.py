# An example that takes a RED (Rare Event Detection) agent through its full lifecycle
# on your own data, in four phases: develop, build, deploy and run.
#
#   Develop: upload the training, validation, test and delivery files. Copy the
#     canonical `red` blueprint into a project and optimize it: each trial averages
#     the windows of each training class into one prototype, and is scored on the
#     labeled validation files. Promote the best trial to a blueprint of your own,
#     then eval that blueprint once on the held-out test files.
#   Build: package the promoted blueprint for the platform.
#   Deploy: deploy the package as batch, and later as serving.
#   Run: on the batch deployment, run a session on the delivery files, whose labels
#     are unknown. On the serving deployment, open a session and query it with the
#     first rows of a delivery file, sent inline.
#
# --data_dir holds one folder per role, each with CSV files (plain or gzipped,
# gzipped ones are unpacked before upload):
# - library/<class>__<name>.csv: training data, one class per file, named by its class:
#   normal operation (the background) and the rare events;
# - validation/*.csv and test/*.csv: labeled by a `label` column, each with the
#   background and at least one event;
# - delivery/*.csv: the data to run the deployed agent on, without labels.
# Every file shares the same columns: the timestamp first, then the sensor channels.
# A window takes the label of its last row.
#
# Default input is example_data/red_pump/: 10 sensor channels of a water pump, sampled
# once a minute, with four breakdowns (no declared licence, see
# example_data/red_pump/README.md).
# usage:
#   python -m examples.agents.agent_red_lifecycle --api_key=<YOUR_API_KEY>
#   python -m examples.agents.agent_red_lifecycle --api_key=<YOUR_API_KEY> --data_dir=<your roles>
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
RED_BLUEPRINT_KEY = "red"
# The column validation and test files carry their labels in.
LABEL_COLUMN = "label"


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
        "ground_truth": {"event": {**ground_truth, "downsampling": "last_record"}},
    }


def categorical(values: list) -> dict:
    """A search space entry trying each of values for a blueprint value."""
    return {"kind": "value", "spec": {"type": "categorical", "values": values}}


def log_event_report(prefix: str, metrics_report: dict, background: str) -> None:
    """Logs the event F1, detection recall and precision, and the false-alarm rate of a metrics report.

    The figures are the report's own. A detection is any event predicted on a window
    with any event, whichever event it is. A window the agent made no prediction for (an
    invalid window) counts as a miss of its true class.
    """
    target = (metrics_report or {}).get("targets", {}).get("event", {})
    names, per_class, aggregate = target.get("class_names"), target.get("per_class"), target.get("aggregate")
    if not names or not per_class or not aggregate or background not in names:
        logging.info(f"{prefix}: {pformat(metrics_report)}")
        return
    b = names.index(background)
    support = per_class["support"]
    # Rows are the true class, columns the predicted class.
    false_alarms = sum(count for p, count in enumerate(target["confusion_matrix"][b]) if p != b)
    unpredicted = sum(target.get("missed") or [])
    logging.info(
        f"{prefix}: foreground_macro_f1={aggregate.get('foreground_macro_f1')} "
        f"detection_recall={aggregate['detection_recall']:.3f} "
        f"detection_precision={aggregate['detection_precision']:.3f} "
        f"false_alarm_rate={false_alarms / max(support[b], 1):.3%} "
        f"({sum(support)} windows, {unpredicted} with no prediction)"
    )


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Each library file holds one class, named by its prefix; the classes the agent
    # classifies over are those. The input columns are read off a labeled file.
    library = role_files(args.data_dir, "library")
    library_classes = [os.path.basename(path).split("__")[0] for path in library]
    events = list(dict.fromkeys(library_classes))
    assert args.background in events, f"No library file for the background class '{args.background}'"
    columns = read_header(role_files(args.data_dir, "validation")[0])
    timestamp_column, data_columns = columns[0], [c for c in columns[1:] if c != LABEL_COLUMN]
    logging.info(f"Classes: {events} (background: {args.background}); data columns: {data_columns}")

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

        library_ids = [upload(path) for path in library]
        validation_ids = [upload(path) for path in role_files(args.data_dir, "validation")]
        test_ids = [upload(path) for path in role_files(args.data_dir, "test")]
        delivery_ids = [upload(path) for path in role_files(args.data_dir, "delivery")]

    # Each training file holds a single class, so its label is a constant. Validation
    # and test files are scored against their label column.
    training_examples = [
        example(file_id, {"from": {"constant": cls}}) for cls, file_id in zip(library_classes, library_ids)
    ]
    validation_examples = [example(file_id, {"from": {"column": LABEL_COLUMN}}) for file_id in validation_ids]

    # Optimize the canonical blueprint. The overrides apply to every trial and carry
    # over to the promoted blueprint: the classes and the background (required by
    # `red`), the input columns and the windowing. Size the window to your events: an
    # event shorter than half a window barely moves it. 64 samples is about an hour of
    # pump data. The search space is what the trials vary: here, the distance to the
    # class prototypes. Trials with the same window share one encoder pass.
    # `foreground_macro_f1` is the F1 over the events alone: the background is most of
    # the data, so `macro_f1` and `accuracy` would mostly score it.
    # Copy the canonical blueprint into the examples project: everything derived from it,
    # the optimization, the promoted blueprint and its package, is then in that project,
    # where the package can be deployed.
    project_id = get_or_create_project(client)
    blueprint_id = get_or_copy_blueprint(
        client, project_id, RED_BLUEPRINT_KEY, f"{RED_BLUEPRINT_KEY}-lifecycle-example"
    )
    optimization = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="foreground_macro_f1",
        training_examples=training_examples,
        validation_examples=validation_examples,
        max_trials=len(args.metrics),
        search_space={"parameters": {"metric": categorical(args.metrics)}},
        overrides={
            "values": {
                "events": events,
                "background": args.background,
                "timestamp_column": timestamp_column,
                "data_columns": data_columns,
                "window_size": args.window_size,
                "step_size": args.step_size,
            }
        },
        name="RED lifecycle example",
    )
    optimization_id = require(optimization, "id")
    logging.info(f"Started optimization_id: {optimization_id}")

    # Wait for every trial to finish, then rank them by their validation score.
    optimization = client.agents.optimizations.wait_until_done(optimization_id, timeout_sec=args.max_run_time_sec)
    logging.info(f"Optimization finished with status: {optimization.get('status')}")
    trials = client.agents.optimizations.list_trials(optimization_id).get("data", [])
    for trial in sorted(trials, key=lambda t: t.get("objective_value") or -1.0, reverse=True):
        log_event_report(
            f"  trial #{trial.get('trial_number')} {trial.get('status')} values={trial.get('trial_values')}",
            trial.get("metrics_report"),
            args.background,
        )
        if trial.get("error"):
            logging.error(f"  trial #{trial.get('trial_number')} error: {trial['error']}")
    best_trial = optimization.get("best_trial")
    if optimization.get("status") != "completed" or not best_trial:
        logging.error(f"Optimization has no winning trial: {pformat(optimization)}")
        return

    # Promote the winner: a blueprint of your own, with the fitted prototypes attached.
    blueprint = client.agents.optimizations.promote_trial(optimization_id, require(best_trial, "id"))
    promoted_id = require(blueprint, "id")
    logging.info(f"Promoted trial #{best_trial.get('trial_number')} to blueprint {blueprint.get('blueprint_key')}")

    # Eval the promoted blueprint once on the held-out test files.
    evaluation = client.agents.evals.create(
        promoted_id,
        examples=[example(file_id, {"from": {"column": LABEL_COLUMN}}) for file_id in test_ids],
        name="RED lifecycle example: test",
    )
    evaluation = client.agents.evals.wait_until_done(require(evaluation, "id"), timeout_sec=args.max_run_time_sec)
    if evaluation.get("status") != "completed":
        logging.error(f"Eval did not complete: {pformat(evaluation)}")
        return
    log_event_report("Test score", evaluation.get("metrics_report"), args.background)

    # Build: package the promoted blueprint, its fitted model resolved once.
    # Deploy and run: deploy the package as batch and run a session on the unlabeled
    # delivery files, one output per file. Then deploy it as serving, and query it with
    # the first delivery file, --rows_per_query rows at a time. The promoted blueprint
    # is kept.
    package_id = build_package(client, promoted_id, name="RED lifecycle example")
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
    parser.add_argument("--data_dir", default="example_data/red_pump", type=str)
    parser.add_argument("--background", default="normal", type=str, help="The class meaning no event happened")
    parser.add_argument("--metrics", default=["cosine", "l1"], type=str, nargs="+", help="One trial per value")
    parser.add_argument("--window_size", default=64, type=int, help="Samples per window")
    parser.add_argument("--step_size", default=1, type=int, help="Samples between window starts")
    parser.add_argument("--rows_per_query", default=96, type=int, help="Delivery rows sent in each serving query")
    parser.add_argument("--num_queries", default=3, type=int, help="Serving queries to send")
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float, help="Per step; negative waits forever")
    args = parser.parse_args(configure_logging=True)

    main(args)
