# An example that demonstrates how to use the Archetype AI image summarization API.
# usage:
#   curl https://live.staticflickr.com/8358/29211988243_82023c5524_b.jpg > test_image.jpg
#   python -m examples.image_summarization --api_key=<YOUR_API_KEY> --filename=test_image.jpg
import argparse
import base64
import logging

from archetypeai.api_client import ArchetypeAI


def base64_encode(filename: str) -> str:
    with open(args.filename, "rb") as img_handle:
        encoded_img = base64.b64encode(img_handle.read()).decode("utf-8")
    return encoded_img


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key)

    # Upload a local file to the Archetype AI platform. Any data uploaded
    # will only be visible and accessible by other members of your org.
    logging.info(f"Uploading {args.filename}")
    encoded_img = base64_encode(args.filename) if args.use_base64 else None
    response_data = client.files.local.upload(args.filename, encoded_img)
    logging.info(f"api response: {response_data}")

    # Use the file ID returned from the upload stage to run the image summarization API.
    file_id = response_data["file_id"]
    logging.info(f"Summarizing {file_id}")
    response_data = client.capabilities.summarize(query=args.query, file_ids=[file_id])

    # Print the summarization results.
    logging.info(response_data["response"]["processed_text"])
    # Print the bounding boxes of any key objects in the image.
    for item in response_data["response"]["bboxes"]:
        logging.info(f"Detected {item['name']}: {item['bbox']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--filename", required=True, type=str)
    parser.add_argument("--query", default="Describe the image", type=str)
    parser.add_argument("--use_base64", default=0, type=int, help="If 1, encodes the image as a base64 string.")
    args = parser.parse_args()
    main(args)