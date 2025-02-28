# An example that demonstrates how to hook up a kafka input/output stream to a lens.
# usage:
#   python -m examples.lens_kafka_io --api_key=<YOUR_API_KEY> --input_topic_id=<YOUR INPUT TOPIC ID>  --output_topic_id=<YOUR OUTPUT TOPIC ID>
import argparse
import logging
from pprint import pformat
import time
import secrets

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
    while True:
        for message in consumer:
            logging.info(message.value)
        if time.time() - start_time > args.max_run_time_sec:
            break
        time.sleep(0.5)

    # Clean up the session.
    response = client.lens.sessions.destroy(session_id)
    logging.info(f"session status: {pformat(response['session_status'], indent=4)}")


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