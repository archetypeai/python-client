# An example that demonstrates how to apply a lens to an image.
# usage:
#   curl https://live.staticflickr.com/8358/29211988243_82023c5524_b.jpg > test_image.jpg
#   python -m examples.lens_image_qa --api_key=<YOUR_API_KEY> --filename=test_image.jpg
import argparse
import logging
from pprint import pformat

from archetypeai.api_client import ArchetypeAI
from archetypeai.utils import base64_encode


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Query the metadata for the specific lens and extract the default lens config.
    lens_metadata = client.lens.get_metadata(lens_id=args.lens_id)
    assert len(lens_metadata) == 1, lens_metadata
    lens_name, lens_config = lens_metadata[0]["lens_name"], lens_metadata[0]["lens_config"]
    logging.info(f"lens name: {lens_name} lens id: {args.lens_id}")

    # Create a new lens session using the specific lens.
    response = client.lens.sessions.create(lens_id=args.lens_id)
    session_id, session_endpoint = response["session_id"], response["session_endpoint"]
    logging.info(f"lens session: {session_id} @ {session_endpoint}")

    # Connect to the lens session.
    is_connected = client.lens.sessions.connect(
        session_id=session_id, session_endpoint=session_endpoint)
    assert is_connected

    # Load the input image and convert it to a base64 encoding.
    base64_img = base64_encode(args.filename)

    # Generate a model query event and send it to the lens.
    event_message = {
        "type": "model.query",
        "event_data": {
            "model_version": lens_config["model_parameters"]["model_version"],
            "template_name": lens_config["model_parameters"]["template_name"],
            "instruction": lens_config["model_parameters"]["instruction"],
            "focus": args.focus,
            "max_new_tokens": args.max_new_tokens,
            "data": [{
                "type": "base64_img",
                "base64_img": base64_img,
            }],
            "sensor_metadata": {}
        }
    }
    logging.info(f"Sending event: {pformat(event_message, indent=4, depth=2)}")
    response = client.lens.sessions.write(session_id, event_message)
    logging.info(f"response: \n {pformat(response, indent=4)}")

    # Clean up the session.
    response = client.lens.sessions.destroy(session_id)
    logging.info(f"session status: {pformat(response['session_status'], indent=4)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-237ab3ffd79199c9", type=str)
    parser.add_argument("--filename", required=True, type=str)
    parser.add_argument("--focus", default="Describe the image.", type=str)
    parser.add_argument("--max_new_tokens", default=256, type=int)
    args = parser.parse_args()
    main(args)