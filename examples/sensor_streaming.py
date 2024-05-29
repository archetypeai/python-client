# An example that demonstrates how to use the Archetype AI sensor streaming API.
# usage:
#   python examples.sensor_streaming --api_key=<YOUR_API_KEY> --sensor_name=example_counter
import argparse
import logging

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint="https://staging.archetypeai.dev/v0.4")

    # Register the sensor with the Archetype AI cloud. Registering your sensor will create
    # a unique sensor ID for this session and open a dedicated endpoint to stream sensor data.
    # Any data or events sent will only be accessible by members as the same org_id as your api_key.
    client.sensors.register(args.sensor_name)

    # Send some example events and data to the cloud. Data and events can be
    # filtered in cloud and other clients via the topic_id.
    logging.info("Sending first event...")
    client.sensors.send(topic_id="sensor_events", data=f"Hi, this is {args.sensor_name}")
    for counter in range(args.num_events):
        logging.info("Sending data...")
        client.sensors.send(topic_id="sensor_data", data={"counter": counter})
    logging.info("Sending last event...")
    client.sensors.send(topic_id="sensor_events", data="See you later...")

    # Cleanly shut down the connection.
    logging.info("Closing connection")
    client.sensors.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--sensor_name", required=True, type=str)
    parser.add_argument("--num_events", default=1000, type=int)
    args = parser.parse_args()
    main(args)