# An example that takes an OSM (Operational State Monitoring) agent through its
# full lifecycle on your own labeled data: optimize, promote, eval, then run.
#
#   1. Upload the training, validation, test and delivery files.
#   2. Optimize the canonical `osm` blueprint: each trial fits a classifier on the
#      training files and is scored on the validation files.
#   3. Promote the best trial to a blueprint of your own.
#   4. Eval that blueprint once on the held-out test files.
#   5. Bundle it and run it on the delivery files, whose labels are unknown.
#
# --data_dir holds one folder per role, each with CSV files (plain or gzipped,
# gzipped ones are unpacked before upload):
# - library/<state>__<name>.csv: training data, one state per file, named by its state;
# - validation/*.csv and test/*.csv: labeled by a `label` column;
# - delivery/*.csv: the data to run the deployed agent on, without labels.
# Every file shares the same columns: the timestamp first, then the sensor channels.
#
# Default input is example_data/osm_larco/: washing machine vibration (9
# accelerometer channels at 200 Hz) labeled fill / wash / spin / drain, derived
# from the LARCO dataset (CC BY 4.0, see example_data/osm_larco/README.md). The
# delivery file comes from a second unit of the same machine model.
#
# To go further on the same data, both repositories below produce a `data/roles/`
# folder in this layout, which you can pass as --data_dir:
# - https://github.com/archetypeai/operational-state-monitoring-agent-example-larco-quickstart
#   prepares the data from the raw dataset: 19 full cycles, about 0.45 GB.
# - https://github.com/archetypeai/operational-state-monitoring-agent-example-larco
#   is the full study: 199 cycles, a 16-trial search and a baseline comparison
#   (25 GB of role files).
# usage:
#   python -m examples.agents.agent_osm_lifecycle --api_key=<YOUR_API_KEY>
#   python -m examples.agents.agent_osm_lifecycle --api_key=<YOUR_API_KEY> --data_dir=<clone>/data/roles
import glob
import gzip
import logging
import os
import shutil
import tempfile

from archetypeai import ArchetypeAI, ArgParser, pformat

from examples.agents.common import require

# The canonical blueprint every optimization starts from.
OSM_BLUEPRINT_KEY = "osm"
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
    with (gzip.open(path, "rt") if path.endswith(".gz") else open(path)) as f:
        return f.readline().strip().split(",")


def labeled_example(file_id: str) -> dict:
    """An example scored against the labels in its `label` column."""
    return {"inputs": [{"type": "file", "id": file_id}], "ground_truth": {"state": {"from": {"column": LABEL_COLUMN}}}}


def categorical(values: list) -> dict:
    """A search space entry trying each of values for a blueprint value."""
    return {"kind": "value", "spec": {"type": "categorical", "values": values}}


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Each library file holds one state, named by its prefix; the states the agent
    # classifies over are those. The input columns are read off a labeled file.
    library = role_files(args.data_dir, "library")
    library_states = [os.path.basename(path).split("__")[0] for path in library]
    states = list(dict.fromkeys(library_states))
    columns = read_header(role_files(args.data_dir, "validation")[0])
    timestamp_column, data_columns = columns[0], [c for c in columns[1:] if c != LABEL_COLUMN]
    logging.info(f"States: {states}; data columns: {data_columns}")

    # Upload the data. Files are always uploaded, replacing any file of the same name,
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

    # Each training file holds a single state, so its label is a constant.
    training_examples = [
        {"inputs": [{"type": "file", "id": file_id}], "ground_truth": {"state": {"from": {"constant": state}}}}
        for state, file_id in zip(library_states, library_ids)
    ]

    # Optimize the canonical blueprint. The overrides apply to every trial and carry
    # over to the promoted blueprint: the states to classify (required by `osm`) and
    # the input columns. The search space is what the trials vary.
    blueprint_id = require(client.agents.blueprints.get(OSM_BLUEPRINT_KEY), "id")
    search_space = {
        "parameters": {
            "window_size": categorical([512]),
            "step_size": categorical([512]),
            "k_neighbors": categorical(args.k_neighbors),
            "metric": categorical(["cosine"]),
            "weights": categorical(["uniform"]),
        }
    }
    optimization = client.agents.optimizations.create(
        blueprint_id=blueprint_id,
        objective="macro_f1",
        training_examples=training_examples,
        validation_examples=[labeled_example(file_id) for file_id in validation_ids],
        max_trials=len(args.k_neighbors),
        search_space=search_space,
        overrides={
            "values": {"states": states, "timestamp_column": timestamp_column, "data_columns": data_columns}
        },
        name="OSM lifecycle example",
    )
    optimization_id = require(optimization, "id")
    logging.info(f"Started optimization_id: {optimization_id}")

    # Wait for every trial to finish, then rank them by their validation score.
    optimization = client.agents.optimizations.wait_until_done(optimization_id, timeout_sec=args.max_run_time_sec)
    logging.info(f"Optimization finished with status: {optimization.get('status')}")
    trials = client.agents.optimizations.list_trials(optimization_id).get("data", [])
    for trial in sorted(trials, key=lambda t: t.get("objective_value") or -1.0, reverse=True):
        logging.info(
            f"  trial #{trial.get('trial_number')} {trial.get('status')}: "
            f"macro_f1={trial.get('objective_value')} values={trial.get('trial_values')}"
        )
        if trial.get("error"):
            logging.error(f"  trial #{trial.get('trial_number')} error: {trial['error']}")
    best_trial = optimization.get("best_trial")
    if optimization.get("status") != "completed" or not best_trial:
        logging.error(f"Optimization has no winning trial: {pformat(optimization)}")
        return

    # Promote the winner: a blueprint of your own, with the fitted classifier attached.
    blueprint = client.agents.optimizations.promote_trial(optimization_id, require(best_trial, "id"))
    promoted_id = require(blueprint, "id")
    logging.info(f"Promoted trial #{best_trial.get('trial_number')} to blueprint {blueprint.get('blueprint_key')}")

    # Eval the promoted blueprint once on the held-out test files.
    evaluation = client.agents.evals.create(
        promoted_id, examples=[labeled_example(file_id) for file_id in test_ids], name="OSM lifecycle example: test"
    )
    evaluation = client.agents.evals.wait_until_done(require(evaluation, "id"), timeout_sec=args.max_run_time_sec)
    if evaluation.get("status") != "completed":
        logging.error(f"Eval did not complete: {pformat(evaluation)}")
        return
    primary = (evaluation.get("metrics_report") or {}).get("primary") or {}
    logging.info(f"Test score: {primary.get('target')}.{primary.get('name')}={primary.get('value')}")

    # Deploy: bundle the promoted blueprint and run it on the unlabeled delivery files,
    # one output per file.
    bundle = client.agents.bundles.create(blueprint=promoted_id, name="OSM lifecycle example")
    agent = client.agents.bundles.run(require(bundle, "id"), source=delivery_ids)
    agent_id = require(agent, "id")
    logging.info(f"Launched agent_id: {agent_id}")
    agent = client.agents.instances.wait_until_done(agent_id, timeout_sec=args.max_run_time_sec)
    if agent.get("status") != "completed":
        events = client.agents.instances.get_events(agent_id)
        logging.error(f"Agent did not complete: {pformat(events)}")
        return
    results = client.agents.instances.get_results(agent_id)
    logging.info(f"Agent results: {pformat(results)}")


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--data_dir", default="example_data/osm_larco", type=str)
    parser.add_argument("--k_neighbors", default=[5, 31], type=int, nargs="+", help="One trial per value")
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float, help="Per step; negative waits forever")
    args = parser.parse_args(configure_logging=True)

    main(args)
