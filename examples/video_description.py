# An example that demonstrates how to use the Archetype AI video description API.
import argparse
import logging
import sys

from archetypeai.api_client import ArchetypeAI

def _validate_result(status_code: int, response_data: dict) -> bool:
    success = status_code == 200
    if not success:
        logging.error(f"Error: {status_code} data: {response_data}")
    return success

def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key)

    # Upload the file to the Archetype AI platform. Any data uploaded
    # will only be accessible by other members of your org.
    logging.info(f"Uploading {args.filename}")
    status_code, response_data = client.upload(args.filename)
    assert _validate_result(status_code, response_data)

    # Use the file ID returned from the upload stage to run the video description API.
    file_id = response_data["file_id"]
    logging.info(f"Describing {file_id}")
    status_code, response_data = client.describe(query=args.query, file_ids=[file_id])
    assert _validate_result(status_code, response_data)

    # Print the description results.
    for result in response_data["response"]:
        logging.info(f"{result['timestamp']}: {result['description']}")


if __name__ == "__main__":
    log_format = "[%(asctime)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S", stream=sys.stdout)
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--filename", required=True, type=str)
    parser.add_argument("--query", default="Describe the video", type=str)
    args = parser.parse_args()
    main(args)