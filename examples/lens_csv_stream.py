# An example that demonstrates how to hook up a CSV file and stream it to a lens.
# usage:
## Upload your CSV file to the Newton Platform:
#   python -m examples.files_api --api_key=<YOUR_API_KEY> --filename=<PATH_TO_LOCAL_CSV>
## Run this example passing in the CSV file_id:
#   python -m examples.lens_csv_stream --api_key=<YOUR_API_KEY> --file_id=<CSV_FILE_ID>
import argparse
import logging
from pprint import pformat
import time
import secrets

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Create and run a new session, using the session function below.
    client.lens.create_and_run_session(
        args.lens_id, session_fn, auto_destroy=True, client=client, args=args)

def session_fn(
        session_id: str,
        session_endpoint: str,
        client: ArchetypeAI,
        args: dict
    ) -> None:
    """Main function to run the logic of a custom lens session."""

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
                "window_size": args.window_size,
                "step_size": args.step_size,
                "loop_recording": args.loop_recording,
                "output_format": "json",
            }
        }
    }
    logging.info(f"Sending event: {pformat(event, indent=4, depth=2)}")
    response = client.lens.sessions.write(session_id, event)
    logging.info(f"response: \n {pformat(response, indent=4)}")

    # Attach a kafka writer as output from the lens.
    topic_uid = secrets.token_hex(8)  # Generate a unique topic for every run.
    topic_id = f"example_csv_data_{topic_uid}"
    event = {
        "type": "output_stream.set",
        "event_data": {
            "stream_type": "kafka_writer",
            "stream_config": {
                "topic_ids": [topic_id],
            }
        }
    }
    logging.info(f"Sending event: {pformat(event, indent=4, depth=2)}")
    response = client.lens.sessions.write(session_id, event)
    logging.info(f"response: \n {pformat(response, indent=4)}")

    # Create a kafka consumer to read the output of the lens, which will contain
    # the CSV rows.
    consumer = client.kafka.create_consumer(
        topic_id=topic_id,
        auto_offset_reset="earliest",
        consumer_timeout_ms=1000,
        consumer_message_batch_size=10,
    )

    start_time = time.time()
    while time.time() - start_time < args.max_run_time_sec:
        for message in consumer:
            logging.info(message.value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file_id", required=True, type=str)
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-237ab3ffd79199b1", type=str)
    parser.add_argument("--max_run_time_sec", default=10.0, type=float)
    parser.add_argument("--window_size", default=1, type=int)
    parser.add_argument("--step_size", default=1, type=int)
    parser.add_argument("--loop_recording", default=0, type=int)
    args = parser.parse_args()
    main(args)