# An example that demonstrates using a webcam as input for a lens
# usage:
#   python tutorial02.py --api_key=<YOUR_API_KEY> --lens_id=<LENS_ID>
import argparse
import logging
import base64
import threading
import cv2
import imutils

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

    # Open the camera
    logging.info("")
    log_heading("Open the camera")
    logging.info("*** Press 'Q' to end the session ***")
    logging.info("")
    camera = cv2.VideoCapture(args.camera_index)
    
    # Try to get the first frame
    if camera.isOpened():
        ret_val, frame = camera.read()
    else:
        ret_val = False

    # Init thread
    stop_event = threading.Event()
    processing_thread = None

    while ret_val:
        ret_val, frame = camera.read()
        if frame is None:
            continue
        
        cv2.imshow('Video Stream', frame)
        
        if processing_thread is None or not processing_thread.is_alive():
            processing_thread = threading.Thread(target=run_thread, args=(stop_event, client, lens_config, session_id, frame))
            processing_thread.daemon = True
            processing_thread.start()

        # Press q to end
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    camera.release()
    cv2.destroyAllWindows()

    # --------------------------------------------------------------------------
    # Destroy lens session
    destroy_lens_session(client, session_id)

    # Clean up
    if processing_thread is not None and processing_thread.is_alive():
        stop_event.set()
        processing_thread.join()

# -----------------------------------------------------------------------------

def log_heading(heading):
    logging.info(f"\x1b[35m--- {heading} ---\x1b[32m")

def destroy_lens_session(client, session_id):
    debug = args.debug

    log_heading("Destroy lens session")
    response = client.lens.sessions.destroy(session_id)
    if debug: logging.info(f"{response}")
    logging.info(f"Session Status: {response['session_status']}")

def run_thread(stop_event, client, lens_config, session_id, frame):
    send_frame(client, lens_config, session_id, frame)
    get_response(stop_event, client, session_id)

def send_frame(client, lens_config, session_id, frame):
    # Resize
    frame = imutils.resize(frame, width=160, height=90)
    
    # DEBUG
    cv2.imwrite("frame.jpg", frame)
    frame_shape = frame.shape
    #logging.info(f"Data size: {frame_shape}")

    # base 64 encode
    # im_arr: image in Numpy one-dim array format.
    im_arr = cv2.imencode('.jpg', frame)[1]
    im_bytes = im_arr.tobytes()
    base64_img = base64.b64encode(im_bytes).decode("utf-8")

    instruction = ""
    if ("instruction" in lens_config["model_parameters"]):
        instruction = lens_config["model_parameters"]["instruction"]
    
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

    response = client.lens.sessions.write(session_id, event_message)
    if ("message" in response):
        logging.info(f"Response: {response}")
        logging.info("*** Press 'Q' to end the session ***")
    
# Keep looping until there is a response
def get_response(stop_event, client, session_id):
    debug = args.debug
    while not stop_event.is_set():
        response = client.lens.sessions.read(session_id)
        if debug: logging.info(f"Response: {response}")

        if response["event_data"] is not None:
            event_data = response["event_data"]["event_data"]

            if "message" in event_data and event_data["message"].startswith("Inference") and not stop_event.is_set():
                logging.info("")
                logging.info(f'{event_data["message"]}')
                break

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--api_key", required=True, type=str, help="set the API key")
    parser.add_argument("-ae", "--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str, help="set the API endpoint")
    parser.add_argument("-l", "--lens_id", required=True, type=str, help="set the lens ID")
    parser.add_argument("-f", "--focus", default="Describe the image.", type=str, help="set the focus of the lens (string)")
    parser.add_argument("-c", "--camera_index", default=0, type=int, help="set the camera index")
    parser.add_argument("-t", "--max_new_tokens", default=256, type=int, help="set the max new")
    parser.add_argument("-d", "--debug", action="store_true", help="show debug information")
    args = parser.parse_args()
    main(args)