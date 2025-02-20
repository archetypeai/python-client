# An example that demonstrates how to use the Archetype AI files API.
# usage:
#   curl https://live.staticflickr.com/8358/29211988243_82023c5524_b.jpg > test_image.jpg
#   python -m examples.files_api --api_key=<YOUR_API_KEY> --filename=test_image.jpg
import argparse
import logging

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Upload a local file to the Archetype AI platform. Any data uploaded
    # will only be visible and accessible by other members of your org.
    logging.info(f"Uploading {args.filename}")
    response_data = client.files.local.upload(args.filename)
    logging.info(f"api response: {response_data}")

    # Retrieve high-level information about all files across your org in the Archetype AI platform.
    logging.info(f"Checking file info")
    response_data = client.files.get_info()
    logging.info(f"api response: {response_data}")

    # List metadata for all files visible across your org in the Archetype AI platform.
    logging.info(f"Checking file metadata")
    response_data = client.files.get_metadata()
    logging.info(f"api response: {response_data}")

    # List just a subset of files, breaking the files into groups, and returning the first shard.
    logging.info(f"Checking file metadata")
    response_data = client.files.get_metadata(shard_index=0, max_items_per_shard=10)
    logging.info(f"api response: {response_data}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--filename", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    args = parser.parse_args()
    main(args)