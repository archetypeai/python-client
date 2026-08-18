# An example that runs an OSM (Operational State Monitoring) agent on sensor data
# using a platform-hosted quick-start bundle.
#
# Lifecycle today: bundles -> instances (discover the bundle, run it, read results).
# Full blueprints -> bundles -> instances support is coming soon.
#
# Default input is example_data/osm_quick_start_drilling_log.csv (Equinor Volve
# drilling telemetry, six operational states). Pass --filename for your own data:
# it must carry the same columns, in the same order, as the data this bundle's
# decoder was trained on, and should be sampled at a similar rate. Windowing
# (window and step size) is applied by the bundle itself, not read from the file.
# usage:
#   python -m examples.agents.agent_osm --api_key=<YOUR_API_KEY>
import logging

from archetypeai import ArchetypeAI, ArgParser, pformat

from examples.agents.common import get_or_upload_file, pick_bundle, require

# Platform OSM quick-start bundle name.
OSM_BUNDLE_NAME = "OSM Quick Start (Volve Six State)"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Fetch the bundle by id if given, else discover the quick-start bundle by name.
    bundle = client.agents.bundles.get(args.bundle_id) if args.bundle_id else pick_bundle(client, OSM_BUNDLE_NAME)
    bundle_id = require(bundle, "id")
    logging.info(f"Using bundle_id: {bundle_id}")

    # Use the sensor log if it is already on the platform, otherwise upload it.
    file_id = get_or_upload_file(client, args.filename)

    # Run the bundle, launching a new agent instance with the uploaded file as input.
    agent = client.agents.bundles.run(bundle_id, source=[file_id])
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

    # Read back the results produced by the agent.
    results = client.agents.instances.get_results(agent_id)
    logging.info(f"Agent results: {pformat(results)}")


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--bundle_id", default="", type=str, help=f"Overrides the '{OSM_BUNDLE_NAME}' bundle")
    parser.add_argument("--filename", default="example_data/osm_quick_start_drilling_log.csv", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
