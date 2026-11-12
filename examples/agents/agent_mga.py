# An example that runs a Manual Generation (MGA) agent on a procedure video using
# a canonical blueprint.
#
# Lifecycle: blueprints -> packages -> deployments -> sessions
#   copy the blueprint into your project, build a package, deploy it as batch,
#   run a session, read results.
#
# Default input is example_data/mga_quick_start_ac_capacitor.mp4 (replacing an
# air conditioner capacitor). Pass --filename for your own video.
# usage:
#   python -m examples.agents.agent_mga --api_key=<YOUR_API_KEY>
import logging
import uuid

from archetypeai import ArchetypeAI, ArgParser

from examples.agents.common import get_or_copy_blueprint, get_or_create_project, get_or_upload_file, run_batch

# Canonical Manual Generation blueprint key.
MGA_BLUEPRINT_KEY = "mga"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Use the procedure video if it is already on the platform, otherwise upload it.
    file_id = get_or_upload_file(client, args.filename)

    # Run the blueprint by id if given, else the canonical one. It is copied into the
    # examples project once, then packaged, deployed and run on the video.
    reference = args.blueprint_id or MGA_BLUEPRINT_KEY
    logging.info(f"Using blueprint: {reference}")
    project_id = get_or_create_project(client)
    blueprint_id = get_or_copy_blueprint(client, project_id, reference, f"{reference}-example")
    run_batch(
        client,
        blueprint_id,
        package_name=args.name or f"manual_generation_quick_start_{uuid.uuid4().hex[:8]}",
        source=[file_id],
        max_run_time_sec=args.max_run_time_sec,
    )


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--blueprint_id", default="", type=str, help=f"Overrides the {MGA_BLUEPRINT_KEY} blueprint")
    parser.add_argument("--name", default="", type=str, help="Friendly name for the built package")
    parser.add_argument("--filename", default="example_data/mga_quick_start_ac_capacitor.mp4", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
