# An example that demonstrates how to use the Archetype AI files API.
# usage:
#   curl https://live.staticflickr.com/8358/29211988243_82023c5524_b.jpg > test_image.jpg
#   python -m examples.files_api --api_key=<YOUR_API_KEY> --filename=test_image.jpg
import logging

from archetypeai import ArchetypeAI, ArgParser


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

    # List the first page of file metadata (newest first, up to 100 files) with the cursors to page on.
    logging.info(f"Checking file metadata")
    response_data = client.files.get_metadata()
    logging.info(f"api response: {response_data}")

    # Page through the files 10 at a time: pass a page's next_cursor as `after` to get the following one.
    logging.info(f"Checking file metadata")
    page = client.files.get_metadata(limit=10)
    while page["has_more"]:
        page = client.files.get_metadata(limit=10, after=page["next_cursor"])
        logging.info(f"api response: {page}")

    # Or walk every file without handling cursors yourself.
    for file_metadata in client.files.iter_metadata():
        logging.info(f"file: {file_metadata['file_id']}")


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--filename", required=True, type=str)
    args = parser.parse_args(configure_logging=True)
    main(args)