# An example that demonstrates how to query the status of current lenses.
# usage:
#   python -m examples.lens_status --api_key=<YOUR_API_KEY>
import argparse
import logging

from archetypeai.api_client import ArchetypeAI
from archetypeai.utils import pformat


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Query the high level info about all lenses.
    lens_info = client.lens.get_info()
    logging.info(f"lens info: \n {pformat(lens_info)}")

    # Query the metadata for each lenses.
    lens_metadata = client.lens.get_metadata()
    logging.info(f"lens metadata: \n {pformat(lens_metadata)}")

    # Query the high level info about all lens sessions.
    session_info = client.lens.sessions.get_info()
    logging.info(f"session info: \n {pformat(session_info)}")

    # Query the metadata for each lens sessions.
    session_metadata = client.lens.sessions.get_metadata()
    logging.info(f"session metadata: \n {pformat(session_metadata)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    args = parser.parse_args()
    main(args)