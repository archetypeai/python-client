# An example that demonstrates changing the focus of a lens
# usage:
#   python quickstart.py --api_key=<YOUR_API_KEY> --lens_id=<LENS_ID> --filename=<FILENAME>
import argparse
import logging
import sys

from archetypeai.api_client import ArchetypeAI
from archetypeai.utils import base64_encode

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
    # Extract the default values from the lens.
    lens_config = read_default_lens_config(client, args.lens_id)

    # Query the status of the session.
    log_heading("Get session status")
    event = {"type": "session.status"}
    response = client.lens.sessions.process_event(session_id, event)
    logging.debug(response)

    # Validate the session.
    log_heading("Validate the session")
    event = {"type": "session.validate"}
    response = client.lens.sessions.process_event(session_id, event)
    logging.debug(f"{response}")
    if "message" in response:
        logging.error(response["message"])
        return
    elif "event_data" in response and response["event_data"]["is_valid"] == False:
        logging.error(response["event_data"]["error_messages"])
        return

    # Load the input image and convert it to a base64 encoding.
    try:
        base64_img = base64_encode(args.filename)
    except FileNotFoundError as err:
        logging.exception(f"Failed to read file {args.filename}")
        return

    instruction = ""
    if "instruction" in lens_config["model_parameters"]:
        instruction = lens_config["model_parameters"]["instruction"]

    # Create a model query event and send this directly to the lens.
    event = {
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
    response = client.lens.sessions.process_event(session_id, event)
    logging.debug(response)

    # Show the description of the image
    log_heading("Response")
    if (response["event_data"] is not None
          and "response" in response["event_data"]):
        logging.info(response["event_data"]["response"])
    else:
        logging.info(response["event_data"])

def read_default_lens_config(client: ArchetypeAI, lens_id: str) -> dict:
    """Queries the metadata for a specific lens and returns the lens config."""
    log_heading("Get lens metadata")
    try:
        lens_metadata = client.lens.get_metadata(lens_id=lens_id)
    except ValueError as err:
        logging.exception(f"Failed to fetch metadata for lens {lens_id}")
        exit()
    assert len(lens_metadata) == 1, lens_metadata
    lens_name = lens_metadata[0]["lens_name"]
    lens_config = lens_metadata[0]["lens_config"]
    lens_model = lens_config["model_parameters"]["model_version"]
    logging.info(f"Lens ID   : {lens_id} ")
    logging.info(f"Lens name : {lens_name}")
    logging.info(f"Lens model: {lens_model}")
    return lens_config

def log_heading(heading: str) -> None:
    logging.info(f"\x1b[35m--- {heading} ---\x1b[32m")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str, help="Set your Archetype API key")
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str, help="Set the API endpoint")
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-237ab3ffd79199c9", type=str, help="Set the lens ID")
    parser.add_argument("--filename", required=True, type=str, help="Set the local filename")
    parser.add_argument("--focus", default="Describe the image.", type=str, help="Set the focus of the lens")
    parser.add_argument("--max_new_tokens", default=256, type=int, help="set the max new")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    args = parser.parse_args()
    log_level = logging.DEBUG if args.debug else logging.INFO
    log_formatter = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(level=log_level, stream=sys.stdout, format=log_formatter, datefmt="%H:%M:%S")
    main(args)