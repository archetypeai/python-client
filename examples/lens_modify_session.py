# An example that demonstrates how to fetch and modify the focus of an active lens session.
# usage:
#   python -m examples.lens_modify_session --api_key=<YOUR_API_KEY>
import logging

from archetypeai import ArchetypeAI, ArgParser


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Create a custom lens with an initial focus of 'cars' and automatically launch the lens session.
    client.lens.create_and_run_lens(f"""
       lens_name: Example Lens
       lens_config:
        model_parameters:
            model_version: Newton::c2_3_7b_2508014e10af56
            focus: cars
    """, session_callback, client=client, args=args)

def session_callback(
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
    parser = ArgParser()
    args = parser.parse_args(configure_logging=True)
    main(args)