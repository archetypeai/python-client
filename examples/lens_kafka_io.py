# An example that demonstrates how to hook up a kafka input/output stream to a lens.
# usage:
## Run the kafka producer to generate some example messages:
#   python -m examples.kafka_producer --api_key=<YOUR_API_KEY> --topic_id=<YOUR INPUT TOPIC ID>
## Run this example to read those messages and pass them in/out of a lens.
#   python -m examples.lens_kafka_io --api_key=<YOUR_API_KEY> --input_topic_id=<YOUR INPUT TOPIC ID>  --output_topic_id=<YOUR OUTPUT TOPIC ID>
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

    # Attach a kafka reader as input to the lens.
    event = {
        "type": "input_stream.set",
        "event_data": {
            "stream_type": "kafka_reader",
            "stream_config": {
                "topic_ids": [args.input_topic_id],
            }
        }
    }
    response = client.lens.sessions.write(session_id, event)
    if "is_valid" not in response or response["is_valid"] == False:
        logging.error(f"response: \n {pformat(response, indent=4)}")

    # Attach a kafka writer as output from the lens.
    event = {
        "type": "output_stream.set",
        "event_data": {
            "stream_type": "kafka_writer",
            "stream_config": {
                "topic_ids": [args.output_topic_id],
            }
        }
    }
    response = client.lens.sessions.write(session_id, event)
    if "is_valid" not in response or response["is_valid"] == False:
        logging.error(f"response: \n {pformat(response, indent=4)}")

    # Create a kafka consumer to read the output of the lens.
    consumer = client.kafka.create_consumer(
        topic_id=args.output_topic_id,
        auto_offset_reset="earliest",
        consumer_timeout_ms=1000
    )

    start_time = time.time()
    while time.time() - start_time < args.max_run_time_sec:
        for message in consumer:
            logging.info(message.value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-237ab3ffd79199b1", type=str)
    parser.add_argument("--input_topic_id", default="example_input_topic", type=str)
    parser.add_argument("--output_topic_id", default="example_output_topic", type=str)
    parser.add_argument("--max_run_time_sec", default=30, type=float)
    args = parser.parse_args()
    main(args)