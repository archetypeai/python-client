# An example that demonstrates how to use the Archetype AI video description API.
# usage:
#   curl https://v3.cdnpk.net/videvo_files/video/free/2018-04/large_preview/180301_06_B_CityRoam_01.mp4 > test_video.mp4
#   python -m examples.video_description --api_key=<YOUR_API_KEY> --filename=test_video.mp4
import argparse
import logging

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key)

    # Upload a local file to the Archetype AI platform. Any data uploaded
    # will only be visible and accessible by other members of your org.
    logging.info(f"Uploading {args.filename}")
    response_data = client.files.local.upload(args.filename)
    logging.info(f"api response: {response_data}")

    # Use the file ID returned from the upload stage to run the video description API.
    file_id = response_data["file_id"]
    logging.info(f"Summarizing {file_id}")
    response_data = client.capabilities.describe(query=args.query, file_ids=[file_id])

    # Print the description results.
    for result in response_data["response"]:
        logging.info(f"{result['timestamp']}: {result['description']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--filename", required=True, type=str)
    parser.add_argument("--query", default="Describe the video", type=str)
    args = parser.parse_args()
    main(args)