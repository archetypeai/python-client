from typing import Optional

import argparse
import base64
import logging
import yaml
import sys

from archetypeai._common import DEFAULT_ENDPOINT


def base64_encode(filename: str) -> str:
    with open(filename, "rb") as img_handle:
        encoded_img = base64.b64encode(img_handle.read()).decode("utf-8")
    return encoded_img


def pformat(data: dict, prefix: str = "") -> str:
    """Prints a dictonary as a formatted yaml string."""
    yaml_string = yaml.dump(data, sort_keys=False, default_flow_style=False)
    fomatted_string = f"{prefix}{yaml_string}"
    return fomatted_string


class ArgParser(argparse.ArgumentParser):
    """Creates a custom arg parser with common ArchetypeAI args."""

    def __init__(self):
        super().__init__(self)
        self.add_argument("--api_key", required=True, type=str, help="Your Archetype AI API key")
        self.add_argument("--api_endpoint", default=DEFAULT_ENDPOINT, type=str, help="The target API endpoint")
        self.add_argument("--logging_level", default=logging.INFO, type=str, help="Sets the logging level")

    def parse_args(self, configure_logging: Optional[bool] = None) -> argparse.Namespace:
        """Configures default logging using optional args."""
        # Call the default arg parser.
        args = super().parse_args()

        # Add a basic logging config if enable.
        if configure_logging:
            logging.basicConfig(level=args.logging_level, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
        
        return args