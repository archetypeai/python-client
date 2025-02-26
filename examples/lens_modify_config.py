# An example that demonstrates how to fetch and modify the focus of a lens.
# usage:
#   python -m examples.lens_modify_config --api_key=<YOUR_API_KEY>
import argparse
import logging
from pprint import pformat

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Create a new lens session using the specific lens.
    response = client.lens.sessions.create(lens_id=args.lens_id)
    session_id, session_endpoint = response["session_id"], response["session_endpoint"]
    logging.info(f"lens session: {session_id} @ {session_endpoint}")

    # Connect to the lens session.
    is_connected = client.lens.sessions.connect(
        session_id=session_id, session_endpoint=session_endpoint)
    assert is_connected

    # Read the current focus of the lens.
    event = {
        "type": "session.get",
        "event_data": {},
    }
    response = client.lens.sessions.write(session_id, event)
    logging.info(f"- old_focus: {response['event_data']['focus']}")

    # Adjust the focus of the lens.
    event = {
        "type": "session.modify",
        "event_data": {
            "focus": "trucks",
        }
    }
    response = client.lens.sessions.write(session_id, event)

    # Read the new focus of the lens.
    event = {
        "type": "session.get",
        "event_data": {},
    }
    response = client.lens.sessions.write(session_id, event)
    logging.info(f"- new_focus: {response['event_data']['focus']}")

    # Clean up the session.
    response = client.lens.sessions.destroy(session_id)
    logging.info(f"session status: {pformat(response['session_status'], indent=4)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-237ab3ffd79199b2", type=str)
    args = parser.parse_args()
    main(args)