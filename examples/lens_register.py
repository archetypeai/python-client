# An example that demonstrates how to define and register a custom lens.
# usage:
#   python -m examples.lens_register --api_key=<YOUR_API_KEY>
import argparse
import logging

import yaml

from archetypeai.api_client import ArchetypeAI
from archetypeai.utils import pformat


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Define a custom lens.
    lens_config = """
       lens_name: Custom Activity Monitor
       lens_config:
        model_pipeline:
        - processor_name: lens_camera_processor
          processor_config: {}
        model_parameters:
            model_version: Newton::c2_1_250408d4362cc9
            instruction: |
                You are a home security safety system. Monitor the real-time camera
                streams and emit security alerts for any suspicous behavior.
            focus: User Behavior
            camera_buffer_size: 5
            camera_buffer_step_size: 5
            min_replicas: 1
            max_replicas: 16
    """
    lens_config = yaml.safe_load(lens_config)

    # Register the custom lens with the Archetype AI platform.
    lens_metadata = client.lens.register(lens_config)
    logging.info(pformat(prefix=f"Lens:\n", data=lens_metadata))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    args = parser.parse_args()
    main(args)