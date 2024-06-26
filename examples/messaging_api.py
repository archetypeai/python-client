# An example that demonstrates how to use the Archetype AI messaging API.
# usage:
#   python -m examples.messaging_api --api_key=<YOUR_API_KEY>
import argparse
import logging

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key)

    # Subscribe to the messaging API and listen for messages on the following topics.
    topic_ids = ["hello", "news"]
    response_data = client.messaging.subscribe(topic_ids)
    logging.info(f"subscribed to topics: {topic_ids} with subscriber id: {response_data['subscriber_uid']}")

    # Broadcast some messages on some specific topic_ids. Only subscribers acros your organization can
    # listen and access these messages.
    client.messaging.broadcast(topic_id="hello", message="world")  # Messages can be strings.
    client.messaging.broadcast(topic_id="hello", message={"foo": "bar"})  # Or small dictionaries.
    client.messaging.broadcast(topic_id="news", message="news of the world")
    client.messaging.broadcast(topic_id="major_tom", message="is there anyone there?")  # No one is subscribed to this.

    # Check for new messages on the topics we subscribed above.
    messages = client.messaging.get_next_messages()
    logging.info(f"Received {len(messages)}:")
    for message in messages:
        logging.info(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    args = parser.parse_args()
    main(args)