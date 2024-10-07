# An example that demonstrates how to use the Archetype AI sensors API to listen to sensor data.
# usage:
#   python -m examples.sensor_subscriber --api_key=<YOUR_API_KEY> --sensor_name=example_counter
import argparse
import logging
import sys
import os
import time

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key)

    # Subscribe to a sensor from the Archetype AI cloud. Clients can only subscribe to
    # sensors within the same org_id as your api_key.
    client.sensors.subscribe(args.sensor_name)

    # Read incoming events from the sensor.
    counter = 0
    while counter < args.num_messages_to_receive:
        for event in client.sensors.get_sensor_data():
            logging.info(f"topic_id: {event['topic_id']} keys: {event['data'].keys()}")
            counter += 1

    # Cleanly shut down the connection.
    client.sensors.close()


if __name__ == "__main__":
    log_format = "[%(asctime)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S", stream=sys.stdout)
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--sensor_name", required=True, type=str)
    parser.add_argument("--num_messages_to_receive", default=10, type=int)
    args = parser.parse_args()
    main(args)