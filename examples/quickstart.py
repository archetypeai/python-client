# An example that demonstrates changing the focus of a lens
# usage:
#   python quickstart.py --api_key=<YOUR_API_KEY> --lens_id=<LENS_ID>
import argparse
import logging

from atai.clients.archetypeai.client import ArchetypeAI
from archetypeai.utils import base64_encode

logger = logging.getLogger("quickstart")

def main(args):
    if args.debug: logger.setLevel(logging.DEBUG)

    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Create a new session based on this lens.
    session_id, session_endpoint = create_session(client, args.lens_id)

    try:
        # Connect to the lens and run the custom session.
        connect_and_run_session(client, session_id, session_endpoint, args)
    finally:
        # Clean up the lens at the end of the session.
        destroy_lens_session(client, session_id)

def create_session(client: ArchetypeAI, lens_id: str):
    """Creates a session and returns the session_id and session_endpoint."""
    log_heading("Create lens session")
    try:
        response = client.lens.sessions.create(lens_id)
        logger.debug(f"{response}")
        if "errors" in response:
            raise ValueError(response["errors"])
    except ValueError as err:
        logger.exception(f"{err}")
        exit()

    # Extract the session_id and endpoint.
    session_id = response["session_id"]
    session_endpoint = response["session_endpoint"]
    logger.info(f"Session ID: {session_id} @ {session_endpoint}")
    return session_id, session_endpoint

def connect_and_run_session(
        client: ArchetypeAI,
        session_id: str,
        session_endpoint: str,
        args: dict
    ) -> bool:

    # Extract the default values from the lens.
    lens_config = read_default_lens_config(client, args.lens_id)

    # Connect to the session.
    log_heading("Connect to the session")
    response = client.lens.sessions.connect(session_id, session_endpoint)
    logger.debug(response)

    # Query the status of the session.
    log_heading("Get session status")
    event_message = {"type": "session.status"}
    response = client.lens.sessions.write(session_id, event_message)
    logger.debug(response)

    # Validate the session.
    log_heading("Validate the session")
    event_message = {"type": "session.validate"}
    response = client.lens.sessions.write(session_id, event_message)
    logger.debug(f"{response}")
    if "message" in response:
        logger.error(response["message"])
        return False
    elif "event_data" in response and response["event_data"]["is_valid"] == False:
        logger.error(response["event_data"]["error_messages"])
        return False

    # Load the input image and convert it to a base64 encoding.
    try:
        base64_img = base64_encode(args.filename)
    except FileNotFoundError as err:
        logger.exception(f"Failed to read file {args.filename}")
        return False

    instruction = ""
    if "instruction" in lens_config["model_parameters"]:
        instruction = lens_config["model_parameters"]["instruction"]

    # Create a model query event and send this directly to the lens.
    event_message = {
        "type": "model.query",
        "event_data": {
            "model_version": lens_config["model_parameters"]["model_version"],
            "template_name": lens_config["model_parameters"]["template_name"],
            "instruction": instruction,
            "focus": args.focus,
            "max_new_tokens": args.max_new_tokens,
            "data": [{
                    "type": "base64_img",
                    "base64_img": base64_img,
            }  ],
            "sensor_metadata": {}
        }
    }
    log_heading("Running prediction")
    response = client.lens.sessions.write(session_id, event_message)
    logger.debug(response)

    # Show the description of the image
    log_heading("Response")
    if (response["event_data"] is not None
          and "response" in response["event_data"]):
        logger.info(response["event_data"]["response"])
    else:
        logger.info(response["event_data"])

    return True

def destroy_lens_session(client: ArchetypeAI, session_id: str) -> None:
    """Cleanly stops and destroys an active session."""
    log_heading("Destroy lens session")
    response = client.lens.sessions.destroy(session_id)
    logger.debug(response)
    logger.info(f"Session Status: {response['session_status']}")

def read_default_lens_config(client: ArchetypeAI, lens_id: str) -> dict:
    """Queries the metadata for a specific lens and returns the lens config."""
    log_heading("Get lens metadata")
    try:
        lens_metadata = client.lens.get_metadata(lens_id=lens_id)
    except ValueError as err:
        logger.exception(f"Failed to fetch metadata for lens {lens_id}")
        exit()
    assert len(lens_metadata) == 1, lens_metadata
    lens_name = lens_metadata[0]["lens_name"]
    lens_config = lens_metadata[0]["lens_config"]
    lens_model = lens_config["model_parameters"]["model_version"]
    logger.info(f"Lens ID   : {lens_id} ")
    logger.info(f"Lens name : {lens_name}")
    logger.info(f"Lens model: {lens_model}")
    return lens_config

def log_heading(heading: str) -> None:
    logger.info(f"\x1b[35m--- {heading} ---\x1b[32m")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str, help="Set your Archetype API key")
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str, help="Set the API endpoint")
    parser.add_argument("--lens_id", required=True, type=str, help="Set the lens ID")
    parser.add_argument("--filename", required=True, type=str, help="Set the local filename")
    parser.add_argument("--focus", default="Describe the image.", type=str, help="Set the focus of the lens")
    parser.add_argument("--max_new_tokens", default=256, type=int, help="set the max new")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    args = parser.parse_args()
    main(args)