# An example that demonstrates how to define and register a custom lens.
# usage:
#   python -m examples.lens_register --api_key=<YOUR_API_KEY>
import logging

import yaml

from archetypeai import ArchetypeAI, ArgParser, pformat


def main(args):
    # Create a new client using you unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Define a custom lens.
    lens_config = """
       lens_name: Custom Activity Monitor
       lens_config:
        model_parameters:
            model_version: Newton::c2_1_250408d4362cc9
            instruction: |
                You are a home security safety system. Monitor the real-time camera
                streams and emit security alerts for any suspicous behavior.
            focus: User Behavior
    """
    lens_config = yaml.safe_load(lens_config)

    # Register the custom lens with the Archetype AI platform.
    lens_metadata = client.lens.register(lens_config)
    logging.info(pformat(prefix=f"Lens:\n", data=lens_metadata))


if __name__ == "__main__":
    parser = ArgParser()
    args = parser.parse_args(configure_logging=True)
    main(args)