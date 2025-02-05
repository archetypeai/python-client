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

    response = client.lens.sessions.create(lens_id=args.lens_id)
    logging.info(f"session metadata: \n {pformat(response, indent=4)}")

    # Store the session_id and endpoint.
    session_id, session_endpoint = response["session_id"], response["session_endpoint"]

    # Connect to the lens session.
    is_connected = client.lens.sessions.connect(
        session_id=session_id, session_endpoint=session_endpoint)
    assert is_connected

    # Load the input image and convert it to a base64 encoding.
    base64_img = base64_encode(args.filename)

    # Generate a model query event and send it to the Archetype platform.
    event_message = {
        "type": "model.query",
        "event_data": {
            "model_version": "Newton::c1_6_241117d4362cc9",
            "template_name": "image_qa_template_task",
            "instruction": "Answer the following question about the image:",
            "focus": "Describe the image.",
            "max_new_tokens": 512,
            "data": [{
                    "type": "base64_img",
                    "base64_img": base64_img,
            }  ],
            "sensor_metadata": {}
        }
    }
    logging.info("Sending event...")
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
    args = parser.parse_args()
    main(args)