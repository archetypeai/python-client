# An example that demonstrates how to hook up a CSV file and stream it to a lens.
# usage:
#   python -m examples.files_api --api_key=<YOUR_API_KEY> --filename=<PATH_TO_LOCAL_CSV>
#   python -m examples.lens_csv_stream --api_key=<YOUR_API_KEY> --file_id=<CSV_FILE_ID>
import argparse
import logging
from pprint import pformat
import time

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Create a new lens session using the specific lens.
    response = client.lens.sessions.create(lens_id=args.lens_id)
    session_id, session_endpoint = response["session_id"], response["session_endpoint"]
    logging.info(f"lens session: {session_id} @ {session_endpoint}")

    # Connect to the lens session.
    is_connected = client.lens.sessions.connect(
        session_id=session_id, session_endpoint=session_endpoint)
    assert is_connected

    # Attach a CSV file reader as input to the lens.
    event = {
        "type": "input_stream.set",
        "event_data": {
            "stream_type": "csv_file_reader",
            "stream_config": {
                "file_id": args.file_id,
            }
        }
    }
    logging.info(f"Sending event: {pformat(event, indent=4, depth=2)}")
    response = client.lens.sessions.write(session_id, event)
    logging.info(f"response: \n {pformat(response, indent=4)}")

    start_time = time.time()
    while True:
        # Read the latest logs from the lens.
        response = client.lens.sessions.read(session_id)
        if response["event_data"] is not None:
            event = response["event_data"]
            logging.info(f"response: \n {pformat(event, indent=4)}")
        if time.time() - start_time > args.max_run_time_sec:
            break
        time.sleep(0.5)

    # Clean up the session.
    response = client.lens.sessions.destroy(session_id)
    logging.info(f"session status: {pformat(response['session_status'], indent=4)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file_id", required=True, type=str)
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-237ab3ffd79199b1", type=str)
    parser.add_argument("--max_run_time_sec", default=10.0, type=float)
    args = parser.parse_args()
    main(args)