# An example that demonstrates how to use the sensor streaming API.
import argparse
import logging
import sys

from archetypeai.sensor_client import SensorClient

def main(args):
    # Create a new client using you unique API key.
    client = SensorClient(args.api_key)

    # Register the sensor with the Archetype AI cloud. Registering your sensor will create
    # a unique sensor ID for this session and open a dedicated endpoint to stream sensor data.
    # Any data or events sent will only be accessible by members as the same org_id as your api_key.
    client.register(args.sensor_name)

    # Send some example events and data to the cloud. Data and events can be
    # filtered in cloud and other clients via the topic_id.
    client.send(topic_id="sensor_events", data=f"Hi, this is {args.sensor_name}")
    for counter in range(args.num_events):
        client.send(topic_id="sensor_data", data={"counter": counter})
    client.send(topic_id="sensor_events", data="See you later...")

    # Cleanly shut down the connection.
    client.close()


if __name__ == "__main__":
    log_format = "[%(asctime)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S", stream=sys.stdout)
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--sensor_name", required=True, type=str)
    parser.add_argument("--num_events", default=1000, type=int)
    args = parser.parse_args()
    main(args)