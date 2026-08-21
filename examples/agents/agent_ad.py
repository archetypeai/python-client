# An example that runs an AD (Anomaly Discovery) agent on sensor data using a
# platform-hosted quick-start bundle.
#
# Lifecycle today: bundles -> instances (discover the bundle, run it, read results).
# Full blueprints -> bundles -> instances support is coming soon.
#
# Default input is example_data/ad_quick_start_bearing_log.csv (IMS run-to-failure
# bearing vibration: one healthy snapshot and one failing snapshot, recorded days
# apart). Pass --filename for your own data: it must carry the same columns, in
# the same order, as the data this bundle's detector was fit on, and should be
# sampled at a similar rate. Windowing (window and step size) is applied by the
# bundle itself, not read from the file.
# usage:
#   python -m examples.agents.agent_ad --api_key=<YOUR_API_KEY>
import logging

from archetypeai import ArchetypeAI, ArgParser, pformat

from examples.agents.common import get_or_upload_file, pick_bundle, require

# Platform AD quick-start bundle name.
AD_BUNDLE_NAME = "AD Quick Start (Bearing Breakdown)"


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Fetch the bundle by id if given, else discover the quick-start bundle by name.
    bundle = client.agents.bundles.get(args.bundle_id) if args.bundle_id else pick_bundle(client, AD_BUNDLE_NAME)
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

    # Read back the results produced by the agent (per-window labels and anomaly scores).
    results = client.agents.instances.get_results(agent_id)
    logging.info(f"Agent results: {pformat(results)}")


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--bundle_id", default="", type=str, help=f"Overrides the '{AD_BUNDLE_NAME}' bundle")
    parser.add_argument("--filename", default="example_data/ad_quick_start_bearing_log.csv", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
