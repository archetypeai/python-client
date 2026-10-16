# An example that runs a Manual Generation (MGA) agent on a procedure video using
# a canonical blueprint and a newly created org-owned bundle.
#
# Lifecycle: blueprints -> bundles -> instances
#   resolve the blueprint, create a bundle, run an instance, read results.
#
# Default input is example_data/mga_quick_start_ac_capacitor.mp4 (replacing an
# air conditioner capacitor). Pass --filename for your own video.
# usage:
#   python -m examples.agents.agent_mga --api_key=<YOUR_API_KEY>
import logging
import uuid

from archetypeai import ArchetypeAI, ArgParser, pformat

from examples.agents.common import get_or_upload_file, require

# Canonical Manual Generation blueprint key.
MGA_BLUEPRINT_KEY = "mga"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # develop: resolve the blueprint by id if given, else by the canonical key.
    blueprint = client.agents.blueprints.get(args.blueprint_id or MGA_BLUEPRINT_KEY)
    blueprint_id = require(blueprint, "id")
    logging.info(f"Using blueprint_id: {blueprint_id}")

    # deploy: create an org-owned bundle pinned to that blueprint, then fetch it by id.
    bundle_name = args.bundle_name or f"manual_generation_quick_start_{uuid.uuid4().hex[:8]}"
    created = client.agents.bundles.create(blueprint=blueprint_id, name=bundle_name)
    bundle_id = require(created, "id")
    client.agents.bundles.get(bundle_id)
    logging.info(f"Using bundle_id: {bundle_id}")

    # Use the procedure video if it is already on the platform, otherwise upload it.
    file_id = get_or_upload_file(client, args.filename)

    # execute: run the bundle, launching a new agent instance with the uploaded video.
    agent = client.agents.bundles.run(bundle_id, source=[file_id])
    agent_id = require(agent, "id")
    logging.info(f"Launched agent_id: {agent_id} status: {agent.get('status', agent)}")

    # Wait for the agent to reach a terminal state (completed, failed, or canceled).
    agent = client.agents.instances.wait_until_done(agent_id, timeout_sec=args.max_run_time_sec)
    status = agent.get("status")
    logging.info(f"Agent finished with status: {status}")

    # `status` is not a reliable terminal signal. A run whose output exists can
    # report `failed` when the job poller flakes, and pods have read `running`
    # for a long time after exiting — so ask /results before concluding the run
    # produced nothing.
    results = client.agents.instances.get_results(agent_id)
    if not results.get("data"):
        events = client.agents.instances.get_events(agent_id)
        logging.error(f"Agent produced no results (status: {status}): {pformat(events)}")
        return
    if status != "completed":
        logging.warning(f"Status is {status} but results exist — treating as succeeded")

    # Read back the results produced by the agent (structured step list).
    results = client.agents.instances.get_results(agent_id)
    logging.info(f"Agent results: {pformat(results)}")


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--blueprint_id", default="", type=str, help=f"Overrides the {MGA_BLUEPRINT_KEY} blueprint")
    parser.add_argument("--bundle_name", default="", type=str, help="Friendly name for the created bundle")
    parser.add_argument("--filename", default="example_data/mga_quick_start_ac_capacitor.mp4", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
