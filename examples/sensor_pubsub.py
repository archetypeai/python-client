# An example that demonstrates how to use the Archetype AI sensor messaging API.
import argparse
import logging
import sys
import os
import time

from archetypeai.sensor_client import SensorClient

def main(args):
    # Create a new client using you unique API key.
    client = SensorClient(args.api_key)

    # Register the sensor with the Archetype AI cloud. Registering your sensor will create
    # a unique sensor ID for this session and open a dedicated endpoint to stream sensor data.
    # Any data or events sent will only be accessible by members as the same org_id as your api_key.
    client.register(args.sensor_name, topic_ids=[args.subscriber_topic_id])

    # Broadcast a message to all clients listening across your org listening on the topic_id.
    logging.info(f"Sending message on topic_id={args.publisher_topic_id}")
    client.send(topic_id=args.publisher_topic_id, data={"message": f"hi, this is {args.sensor_name}"})

    # Listen for incoming messages.
    message_counter = 0
    while message_counter < args.num_messages_to_receive:
        # Consume any messages that were sent to the client.
        for topic_id, data in client.get_messages():
            logging.info(f"Received: topic_id={topic_id} data={data}")
            message_counter += 1
        time.sleep(0.1)

    # Broadcast a closing message to all clients listening across your org listening on the topic_id.
    logging.info(f"Sending message on topic_id={args.publisher_topic_id}")
    client.send(topic_id=args.publisher_topic_id, data={"message": "bye!"})

    # Cleanly shut down the connection.
    client.close()


if __name__ == "__main__":
    log_format = "[%(asctime)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S", stream=sys.stdout)
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--sensor_name", required=True, type=str)
    parser.add_argument("--publisher_topic_id", default="my_messages/", type=str)
    parser.add_argument("--subscriber_topic_id", default="my_messages/", type=str)
    parser.add_argument("--num_messages_to_receive", default=1, type=int)
    args = parser.parse_args()
    main(args)