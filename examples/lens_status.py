# An example that demonstrates how to query the status of current lenses.
# usage:
#   python -m examples.lens_status --api_key=<YOUR_API_KEY>
import logging

from archetypeai import ArchetypeAI, ArgParser, pformat


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
    parser = ArgParser()
    args = parser.parse_args(configure_logging=True)
    main(args)