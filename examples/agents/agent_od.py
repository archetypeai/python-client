# An example that runs an OD (Label-Free Anomaly Discovery) agent on sensor data
# using the canonical `od` blueprint: it scores every window of a file against the
# file's other windows, with no labels, no reference data and nothing fitted ahead of time.
#
# Lifecycle: blueprints -> packages -> deployments -> sessions
#   copy the blueprint into your project with one-hour windows, build a package,
#   deploy it as batch, run a session over your file, read results.
#
# Default input is example_data/od_metropt/metropt_compressor_2020-07.csv.gz (MetroPT-3:
# three weeks of a metro train's air compressor, sampled every 10 seconds, with one air
# leak in the maintenance reports). Pass --filename for your own data: a timestamp
# column first, then the numeric channels. Each output row is one window, with its
# `anomaly_score` and `predicted_label`: a score over 1.5 is labeled `anomaly`. The
# detector flags what is rare, so anomalies should be a small part of the file.
# usage:
#   python -m examples.agents.agent_od --api_key=<YOUR_API_KEY>
import logging
import uuid

from archetypeai import ArchetypeAI, ArgParser

from examples.agents.common import (
    get_or_copy_blueprint,
    get_or_create_project,
    get_or_upload_file,
    run_batch,
)

# Canonical Label-Free Anomaly Discovery blueprint.
OD_BLUEPRINT_KEY = "od"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Use the sensor log if it is already on the platform, otherwise upload it.
    file_id = get_or_upload_file(client, args.filename)

    # Copy the blueprint into the examples project once, with windows of --window_size
    # rows that do not overlap. The copy's key names the window size, so another size
    # makes another copy. It is then packaged, deployed and run on the file.
    reference = args.blueprint_id or OD_BLUEPRINT_KEY
    logging.info(f"Using blueprint: {reference}")
    project_id = get_or_create_project(client)
    blueprint_id = get_or_copy_blueprint(
        client,
        project_id,
        reference,
        f"{reference}-w{args.window_size}-example",
        overrides={"values": {"window_size": args.window_size, "step_size": args.window_size}},
    )
    run_batch(
        client,
        blueprint_id,
        package_name=args.name or f"od_example_{uuid.uuid4().hex[:8]}",
        source=[file_id],
        max_run_time_sec=args.max_run_time_sec,
    )


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--blueprint_id", default="", type=str, help=f"Overrides the {OD_BLUEPRINT_KEY} blueprint")
    parser.add_argument("--name", default="", type=str, help="Friendly name for the built package")
    parser.add_argument("--filename", default="example_data/od_metropt/metropt_compressor_2020-07.csv.gz", type=str)
    parser.add_argument("--window_size", default=360, type=int, help="Rows per window: 360 is one hour at 10 s")
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
