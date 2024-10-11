# An example that demonstrates how to use the Archetype AI sensor streaming API.
# usage:
#   python -m examples.sensor_streaming --api_key=<YOUR_API_KEY> --sensor_name=example_counter
import argparse
import logging
import time
import random

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, num_sensor_threads=1)

    # Register the sensor with the Archetype AI cloud. Registering your sensor will create
    # a unique sensor ID for this session and open a dedicated endpoint to stream sensor data.
    # Any data or events sent will only be accessible by members as the same org_id as your api_key.
    client.sensors.register(args.sensor_name)

    # Send some example events and data to the cloud. Data and events can be
    # filtered in cloud and other clients via the topic_id.
    for counter in range(args.num_events):
        data_values = [random.randint(0, 255) for i in range(args.payload_size)]
        logging.info(f"Sending data. qsize: {client.sensors.get_outgoing_message_queue_size()}")
        client.sensors.send(topic_id="sensor_data", data={"counter": counter, "values": data_values, "timestamp": time.time()})
        time.sleep(0.1)

    # Cleanly shut down the connection.
    logging.info("Closing connection")
    client.sensors.close()

    # Get some stats about the streamed data.
    stats = client.sensors.get_stats()
    logging.info(f"stats: {stats}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--sensor_name", required=True, type=str)
    parser.add_argument("--num_events", default=1000, type=int)
    parser.add_argument("--payload_size", default=1024, type=int)
    args = parser.parse_args()
    main(args)