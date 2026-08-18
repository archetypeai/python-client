# An example that runs a Task Verification (TVA) agent on a task-execution video
# using a canonical blueprint and a newly created org-owned bundle.
#
# Lifecycle: blueprints -> bundles -> instances
#   resolve the blueprint, create a bundle, run an instance, read results.
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

from archetypeai import ArchetypeAI, ArgParser, pformat

from examples.agents.common import get_or_upload_file, require

# Canonical Task Verification blueprint key.
TVA_BLUEPRINT_KEY = "tva"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # develop: resolve the blueprint by id if given, else by the canonical key.
    blueprint = client.agents.blueprints.get(args.blueprint_id or TVA_BLUEPRINT_KEY)
    blueprint_id = require(blueprint, "id")
    logging.info(f"Using blueprint_id: {blueprint_id}")

    # deploy: create an org-owned bundle pinned to that blueprint, then fetch it by id.
    bundle_name = args.bundle_name or f"task_verification_quick_start_{uuid.uuid4().hex[:8]}"
    created = client.agents.bundles.create(blueprint=blueprint_id, name=bundle_name)
    bundle_id = require(created, "id")
    client.agents.bundles.get(bundle_id)
    logging.info(f"Using bundle_id: {bundle_id}")

    # Use the video and procedure steps if they are already on the platform,
    # otherwise upload them.
    video_file_id = get_or_upload_file(client, args.filename)
    steps_file_id = get_or_upload_file(client, args.steps_filename)

    # execute: run the bundle, launching a new agent instance with the video and steps.
    agent = client.agents.bundles.run(bundle_id, source=[video_file_id, steps_file_id])
    agent_id = require(agent, "id")
    logging.info(f"Launched agent_id: {agent_id} status: {agent.get('status', agent)}")

    # Wait for the agent to reach a terminal state (completed, failed, or canceled).
    agent = client.agents.instances.wait_until_done(agent_id, timeout_sec=args.max_run_time_sec)
    status = agent.get("status")
    logging.info(f"Agent finished with status: {status}")

    if status != "completed":
        # Log the agent's event log to help debug the failure.
        events = client.agents.instances.get_events(agent_id)
        logging.error(f"Agent did not complete: {pformat(events)}")
        return

    # Read back the results produced by the agent (per-step verdicts).
    results = client.agents.instances.get_results(agent_id)
    logging.info(f"Agent results: {pformat(results)}")


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--blueprint_id", default="", type=str, help=f"Overrides the {TVA_BLUEPRINT_KEY} blueprint")
    parser.add_argument("--bundle_name", default="", type=str, help="Friendly name for the created bundle")
    parser.add_argument("--filename", default="example_data/tva_quick_start_oring_cap.mp4", type=str)
    parser.add_argument("--steps_filename", default="example_data/tva_quick_start_oring_cap.txt", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
