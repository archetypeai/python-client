# A quick start that runs a Manual Generation (MGA) agent on a short procedure video.
#
# Lifecycle: blueprints -> bundles -> instances
#   upload the video, bundle the canonical `mga` blueprint, run it, read the results.
#
# Default input is example_data/mga_quick_start_ac_capacitor.mp4 (replacing an
# air conditioner capacitor). Pass --filename for your own video.
# usage:
#   python -m examples.quickstart --api_key=<YOUR_API_KEY>
import logging
import uuid

from archetypeai import ArchetypeAI, ArgParser, pformat


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Upload the video file to the Archetype AI platform.
    file_id = client.files.local.upload(args.filename)["file_id"]
    logging.info(f"Uploaded file_id: {file_id}")

    # Bundle the canonical Manual Generation blueprint, ready to run.
    blueprint_id = client.agents.blueprints.get("mga")["id"]
    bundle_name = f"quickstart_{uuid.uuid4().hex[:8]}"
    bundle_id = client.agents.bundles.create(blueprint=blueprint_id, name=bundle_name)["id"]
    logging.info(f"Created bundle_id: {bundle_id}")

    agent_id = None
    try:
        # Run the bundle on the video and wait for the agent to finish.
        agent_id = client.agents.bundles.run(bundle_id, source=[file_id])["id"]
        logging.info(f"Launched agent_id: {agent_id}")
        agent = client.agents.instances.wait_until_done(agent_id, timeout_sec=args.max_run_time_sec)
        status = agent.get("status")
        logging.info(f"Agent finished with status: {status}")

        if status == "completed":
            results = client.agents.instances.get_results(agent_id)
            logging.info(f"Agent results: {pformat(results)}")
        else:
            events = client.agents.instances.get_events(agent_id)
            logging.error(f"Agent did not complete: {pformat(events)}")
    finally:
        # Delete the agent run, then the bundle, so repeated runs do not accumulate them in your org.
        # A bundle cannot be deleted while an agent run still references it.
        if agent_id:
            client.agents.instances.delete(agent_id)
        client.agents.bundles.delete(bundle_id)


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--filename", default="example_data/mga_quick_start_ac_capacitor.mp4", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
