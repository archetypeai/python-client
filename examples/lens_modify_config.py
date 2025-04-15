# An example that demonstrates how to fetch and modify the focus of a lens.
# usage:
#   python -m examples.lens_modify_config --api_key=<YOUR_API_KEY>
import argparse
import logging
from pprint import pformat

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Create and run a new session, using the session function below.
    client.lens.create_and_run_session(
        args.lens_id, session_fn, auto_destroy=True, client=client, args=args)

def session_fn(
        session_id: str,
        session_endpoint: str,
        client: ArchetypeAI,
        args: dict
    ) -> None:
    """Main function to run the logic of a custom lens session."""

    # Read the current focus of the lens.
    event = {
        "type": "session.get",
        "event_data": {},
    }
    response = client.lens.sessions.process_event(session_id, event)
    logging.info(f"- old_focus: {response['event_data']['focus']}")

    # Adjust the focus of the lens.
    event = {
        "type": "session.modify",
        "event_data": {
            "focus": "trucks",
        }
    }
    response = client.lens.sessions.process_event(session_id, event)

    # Read the new focus of the lens.
    event = {
        "type": "session.get",
        "event_data": {},
    }
    response = client.lens.sessions.process_event(session_id, event)
    logging.info(f"- new_focus: {response['event_data']['focus']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-237ab3ffd79199b2", type=str)
    args = parser.parse_args()
    main(args)