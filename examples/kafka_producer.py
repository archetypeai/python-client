import argparse
import logging
import sys

from atai.clients.archetypeai.client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    producer = client.kafka.create_producer(topic_ids=[args.topic_id])

    for counter_value in range(args.num_test_messages):
        logging.info("Sending...")
        producer.send(topic_id=args.topic_id, value={"counter": counter_value})

    producer.flush()


if __name__ == "__main__":
    log_format = "[%(asctime)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S", stream=sys.stdout)

    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str,
                        help="The ATAI api_key that the example will run under.")
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str,
                        help="The ATAI platform the example will connect to.")
    parser.add_argument("--topic_id", default="example_topic", type=str,
                        help="The topic to broadcast messages on.")
    parser.add_argument("--num_test_messages", default=100, type=int,
                        help="The number of messages to broadcast.")
    
    args = parser.parse_args()
    main(args)