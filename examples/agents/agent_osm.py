# An example that runs an OSM (Operational State Monitoring) agent on sensor data
# using a platform demo blueprint: a six-state classifier fit to the Equinor Volve drilling dataset.
#
# Lifecycle: blueprints -> packages -> deployments -> sessions
#   copy the blueprint into your project, build a package, deploy it as batch,
#   run a session over your file, read results.
#
# Default input is example_data/osm_quick_start_volve_f14_log.csv (Equinor Volve
# drilling telemetry, six operational states). Pass --filename for your own data:
# it must carry the same columns, in the same order, as the data this blueprint's
# decoder was trained on, and should be sampled at a similar rate. Windowing
# (window and step size) is set by the blueprint itself, not read from the file.
# usage:
#   python -m examples.agents.agent_osm --api_key=<YOUR_API_KEY>
import logging
import uuid

from archetypeai import ArchetypeAI, ArgParser

from examples.agents.common import (
    get_or_copy_blueprint,
    get_or_create_project,
    get_or_upload_file,
    run_batch,
)

# Platform OSM demo blueprint: the `osm` blueprint with a head the platform fit for demos.
OSM_BLUEPRINT_KEY = "playground-osm-drilling"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Use the sensor log if it is already on the platform, otherwise upload it.
    file_id = get_or_upload_file(client, args.filename)

    # Run the blueprint by id if given, else the demo one. It is copied into the
    # examples project once, then packaged, deployed and run on the file.
    reference = args.blueprint_id or OSM_BLUEPRINT_KEY
    logging.info(f"Using blueprint: {reference}")
    project_id = get_or_create_project(client)
    blueprint_id = get_or_copy_blueprint(client, project_id, reference, f"{reference}-example")
    run_batch(
        client,
        blueprint_id,
        package_name=args.name or f"osm_example_{uuid.uuid4().hex[:8]}",
        source=[file_id],
        max_run_time_sec=args.max_run_time_sec,
    )


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--blueprint_id", default="", type=str, help=f"Overrides the {OSM_BLUEPRINT_KEY} blueprint")
    parser.add_argument("--name", default="", type=str, help="Friendly name for the built package")
    parser.add_argument("--filename", default="example_data/osm_quick_start_volve_f14_log.csv", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
