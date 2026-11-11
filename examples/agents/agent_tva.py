# An example that runs a Task Verification (TVA) agent on a task-execution video
# using a canonical blueprint.
#
# Lifecycle: blueprints -> packages -> deployments -> sessions
#   copy the blueprint into your project, build a package, deploy it as batch,
#   run a session, read results.
#
# TVA takes two inputs: the video to verify and a text file listing the procedure
# steps, one per line. The pair is matched by file name stem, e.g.
# example_data/tva_quick_start_oring_cap.mp4 + tva_quick_start_oring_cap.txt
# (installing an o-ring cap on a manifold). Pass --filename / --steps_filename
# for your own video and procedure.
# usage:
#   python -m examples.agents.agent_tva --api_key=<YOUR_API_KEY>
import logging
import uuid

from archetypeai import ArchetypeAI, ArgParser

from examples.agents.common import get_or_copy_blueprint, get_or_create_project, get_or_upload_file, run_batch

# Canonical Task Verification blueprint key.
TVA_BLUEPRINT_KEY = "tva"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Use the video and procedure steps if they are already on the platform,
    # otherwise upload them.
    video_file_id = get_or_upload_file(client, args.filename)
    steps_file_id = get_or_upload_file(client, args.steps_filename)

    # Run the blueprint by id if given, else the canonical one. It is copied into the
    # examples project once, then packaged, deployed and run on the video and steps.
    reference = args.blueprint_id or TVA_BLUEPRINT_KEY
    logging.info(f"Using blueprint: {reference}")
    project_id = get_or_create_project(client)
    blueprint_id = get_or_copy_blueprint(client, project_id, reference, f"{reference}-example")
    run_batch(
        client,
        blueprint_id,
        package_name=args.name or f"task_verification_quick_start_{uuid.uuid4().hex[:8]}",
        source=[video_file_id, steps_file_id],
        max_run_time_sec=args.max_run_time_sec,
    )


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--blueprint_id", default="", type=str, help=f"Overrides the {TVA_BLUEPRINT_KEY} blueprint")
    parser.add_argument("--name", default="", type=str, help="Friendly name for the built package")
    parser.add_argument("--filename", default="example_data/tva_quick_start_oring_cap.mp4", type=str)
    parser.add_argument("--steps_filename", default="example_data/tva_quick_start_oring_cap.txt", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
