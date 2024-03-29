# An example that demonstrates how to use the image summarization API.
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

    # Use the file ID returned from the upload stage to run the image summarization API.
    file_id = response_data["file_id"]
    logging.info(f"Summarizing {file_id}")
    status_code, response_data = client.summarize(query=args.query, file_ids=[file_id])
    assert _validate_result(status_code, response_data)

    # Print the summarization results.
    logging.info(response_data["response"]["processed_text"])
    # Print the bounding boxes of any key objects in the image.
    for item in response_data["response"]["bboxes"]:
        logging.info(f"Detected {item['name']}: {item['bbox']}")


if __name__ == "__main__":
    log_format = '[%(asctime)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, datefmt='%H:%M:%S', stream=sys.stdout)
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--filename", required=True, type=str)
    parser.add_argument("--query", default='Describe the image', type=str)
    args = parser.parse_args()
    main(args)