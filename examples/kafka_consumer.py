import argparse
import logging
import sys

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    consumer = client.kafka.create_consumer(
        topic_id=args.topic_id,
        auto_offset_reset="earliest",
        consumer_timeout_ms=args.consumer_timeout_ms
    )

    for message in consumer:
        message = message.value
        logging.info(message)


if __name__ == "__main__":
    log_format = "[%(asctime)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S", stream=sys.stdout)

    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str,
                        help="The ATAI api_key that the example will run under.")
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str,
                        help="The ATAI platform the example will connect to.")
    parser.add_argument("--topic_id", default="example_topic", type=str,
                        help="The topic to consume messages from.")
    parser.add_argument("--consumer_timeout_ms", default=1000, type=int,
                        help="The default time the consume should wait for the last message.")
    
    args = parser.parse_args()
    main(args)