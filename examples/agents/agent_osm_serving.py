# An example that serves an OSM (Operational State Monitoring) agent and queries it
# with sensor data, using the platform demo blueprint.
#
# Lifecycle: blueprints -> packages -> deployments -> sessions
#   copy the blueprint into your project, build a package, deploy it as serving,
#   open a session, send it queries, then stop and delete everything.
#
# Each query carries a slice of sensor rows inline: one list of values per data
# column, in the file's column order, without the timestamp. Default input is
# example_data/osm_quick_start_volve_f14_log.csv (Equinor Volve drilling
# telemetry). Pass --filename for your own data, with the same columns.
# usage:
#   python -m examples.agents.agent_osm_serving --api_key=<YOUR_API_KEY>
import logging
import uuid

from archetypeai import ArchetypeAI, ArgParser, pformat

from examples.agents.common import (
    build_package,
    deploy,
    get_or_copy_blueprint,
    get_or_create_project,
    read_channels,
    require,
    tear_down,
)

# Platform OSM demo blueprint: the `osm` blueprint with a head the platform fit for demos.
OSM_BLUEPRINT_KEY = "playground-osm-drilling"


def numeric_query(channels: list[list[float]]) -> dict:
    """A serving query carrying channels inline, the payload the OSM blueprint accepts."""
    return {"query": "", "events": [{"type": "data.numeric_array", "event_data": {"contents": channels}}]}


def describe_window(window: dict, first_row: int) -> str:
    """One window of an answer: its rows in the file, predicted state, and non-zero probabilities."""
    probabilities = {key[len("p_") :]: float(value) for key, value in window.items() if key.startswith("p_")}
    likely = ", ".join(
        f"{state} {p:.2f}" for state, p in sorted(probabilities.items(), key=lambda item: -item[1]) if p > 0
    )
    # The window end is `finish_timestamp`, or `timestamp` where the schema names it so;
    # `start_timestamp` is optional.
    finish = window.get("finish_timestamp", window.get("timestamp"))
    start = window.get("start_timestamp", finish)
    rows = f"rows {first_row + int(start)}-{first_row + int(finish)}" if finish is not None else "window"
    return f"  {rows}: {window.get('predicted_state')} ({likely})"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Copy the blueprint into the examples project once, then package it.
    project_id = get_or_create_project(client)
    reference = args.blueprint_id or OSM_BLUEPRINT_KEY
    blueprint_id = get_or_copy_blueprint(client, project_id, reference, f"{reference}-example")
    package_id = build_package(client, blueprint_id, args.name or f"osm_serving_{uuid.uuid4().hex[:8]}")

    deployment_id = None
    session_ids = []
    try:
        # Deploy the package as serving: the platform places it on a worker.
        deployment_id = deploy(client, package_id, kind="serving")

        # Open a session on the deployment and wait until it can answer queries.
        session = client.agents.sessions.create(deployment_id)
        session_id = require(session, "id")
        session_ids.append(session_id)
        session = client.agents.sessions.wait_until_running(session_id, timeout_sec=args.max_wait_time_sec)
        if session.get("status") != "running":
            logging.error(f"Session is not running: {pformat(session)}")
            return
        logging.info(f"Session {session_id} is running")

        # Send the file in slices of --rows_per_query rows, one query each.
        channels = read_channels(args.filename)
        num_rows = len(channels[0])
        for start in range(0, num_rows, args.rows_per_query):
            window = [channel[start : start + args.rows_per_query] for channel in channels]
            answer = client.agents.sessions.query(session_id, numeric_query(window))
            logging.info(f"Rows {start}-{start + len(window[0]) - 1}: {answer.get('query_response_time_ms')} ms")
            # The answer has one entry per agent window. The demo blueprint also returns
            # each window's embeddings, 768 values per channel: print them with --verbose.
            if args.verbose:
                logging.info(f"Response: {pformat(answer.get('response'))}")
            else:
                for agent_window in (answer.get("response") or {}).get("data", []):
                    logging.info(describe_window(agent_window, start))
    finally:
        # Cancel the session and stop the deployment, then delete them and the package.
        tear_down(client, session_ids, deployment_id, package_id)


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--blueprint_id", default="", type=str, help=f"Overrides the {OSM_BLUEPRINT_KEY} blueprint")
    parser.add_argument("--name", default="", type=str, help="Friendly name for the built package")
    parser.add_argument("--filename", default="example_data/osm_quick_start_volve_f14_log.csv", type=str)
    parser.add_argument("--rows_per_query", default=200, type=int, help="Sensor rows sent in each query")
    parser.add_argument("--max_wait_time_sec", default=300.0, type=float, help="Wait for the session to run")
    parser.add_argument("--verbose", action="store_true", help="Print each full answer, embeddings included")
    args = parser.parse_args(configure_logging=True)

    main(args)
