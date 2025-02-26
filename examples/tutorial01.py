# An example that demonstrates changing a lens
# usage:
#   python tutorial01.py --api_key=<YOUR_API_KEY> --lens_id=<LENS_ID> --filename=<FILENAME>
import argparse
import logging

from archetypeai.api_client import ArchetypeAI
from archetypeai.utils import base64_encode

def main(args):
    debug = args.debug
    
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)
    
    # -------------------------------------------------------------------------
    # Query the metadata for the specific lens and extract the default lens config.
    log_heading("Get lens metadata")
    try:
        lens_metadata = client.lens.get_metadata(lens_id=args.lens_id)
    except ValueError as err:
        logging.error(f"{err}")
        exit()
    assert len(lens_metadata) == 1, lens_metadata
    lens_name = lens_metadata[0]["lens_name"]
    lens_config = lens_metadata[0]["lens_config"]
    lens_model = lens_config["model_parameters"]["model_version"]
    logging.info(f"Lens ID   : {args.lens_id}")
    logging.info(f"Lens name : {lens_name}")
    logging.info(f"Lens model: {lens_model}")

    # -------------------------------------------------------------------------
    # Create, connect and validate a new lens session
    log_heading("Create lens session")
    try:
        response = client.lens.sessions.create(lens_id=args.lens_id)
        if debug: logging.info(f"{response}")
    except ValueError as err:
        logging.error(f"{err}")
        exit()
    
    # Check for errors
    if ("errors" in response):
        logging.error(f'{response["errors"]}')
        exit()

    # Store the session_id and endpoint.
    session_id = response["session_id"]
    session_endpoint = response["session_endpoint"]
    logging.info(f"Session ID: {session_id}")

    # Connect to the session
    if debug: logging.info("--- Connect to the session ---")
    response = client.lens.sessions.connect(session_id, session_endpoint)
    if debug: logging.info(f"{response}")

    # Query the status of the session
    if debug: logging.info("--- Get session status ---")
    event_message = {"type": "session.status"}
    response = client.lens.sessions.write(session_id, event_message)
    if debug: logging.info(f"{response}")

    # Validate the session
    if debug: logging.info("--- Validate the session ---")
    event_message = {"type": "session.validate"}
    response = client.lens.sessions.write(session_id, event_message)
    if debug: logging.info(f"{response}")
    if ("message" in response):
        logging.error(f'{response["message"]}')
        destroy_lens_session(client, session_id)
        exit()
    elif ("event_data" in response and response["event_data"]["is_valid"] == False):
        logging.error(f'{response["event_data"]["error_messages"]}')
        destroy_lens_session(client, session_id)
        exit()
    
    # -------------------------------------------------------------------------
    # Send image
    log_heading("Send image")
    logging.info(f"Filename: {args.filename}")
    # Load the input image and convert it to a base64 encoding.
    try:
        base64_img = base64_encode(args.filename)
    except FileNotFoundError as err:
        logging.error(f"{err}")
        destroy_lens_session(client, session_id)
        exit()
    
    template_name = lens_config["model_parameters"]["template_name"]

    instruction = ""
    if ("instruction" in lens_config["model_parameters"]):
        instruction = lens_config["model_parameters"]["instruction"]

    # Set the focus
    focus = args.focus
    if not focus:
        # Default focus
        if template_name == "image_qa_template_task":
            focus = "Describe the image."
        elif template_name == "image_bbox_template_task":
            focus = "Input: [Cars]"
    
    event_message = {
        "type": "model.query",
        "event_data": {
            "model_version": lens_config["model_parameters"]["model_version"],
            "template_name": lens_config["model_parameters"]["template_name"],
            "instruction": instruction,
            "focus": focus,
            "max_new_tokens": args.max_new_tokens,
            "data": [{
                    "type": "base64_img",
                    "base64_img": base64_img,
            }  ],
            "sensor_metadata": {}
        }
    }
    response = client.lens.sessions.write(session_id, event_message)
    if debug: logging.info(f"{response}")
    if ("message" in response):
        logging.error(f'{response["message"]}')
        destroy_lens_session(client, session_id)
        exit()

    # -------------------------------------------------------------------------
    # Show the description of the image
    log_heading("Response")
    if (response["event_data"] is not None
          and "response" in response["event_data"]):
        logging.info(response["event_data"]["response"])
    else:
        logging.info(response["event_data"])
    
    # -------------------------------------------------------------------------
    # Destroy lens session
    destroy_lens_session(client, session_id)

# -----------------------------------------------------------------------------

def log_heading(heading):
    logging.info(f"\x1b[35m--- {heading} ---\x1b[32m")

def destroy_lens_session(client, session_id):
    debug = args.debug

    log_heading("Destroy lens session")
    response = client.lens.sessions.destroy(session_id)
    if debug: logging.info(f"{response}")
    logging.info(f"Session Status: {response['session_status']}")

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--api_key", required=True, type=str, help="set the API key")
    parser.add_argument("-ae", "--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str, help="set the API endpoint")
    parser.add_argument("-l", "--lens_id", required=True, type=str, help="set the lens ID")
    parser.add_argument("-fn", "--filename", required=True, type=str, help="set the local filename (string)")
    parser.add_argument("-f", "--focus", default="", type=str, help="set the focus of the lens (string)")
    parser.add_argument("-t", "--max_new_tokens", default=256, type=int, help="set the max new")
    parser.add_argument("-d", "--debug", action="store_true", help="show debug information")
    args = parser.parse_args()
    main(args)