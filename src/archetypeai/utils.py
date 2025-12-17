from typing import Optional

import base64
import logging
import yaml
import sys


def base64_encode(filename: str) -> str:
    with open(filename, "rb") as img_handle:
        encoded_img = base64.b64encode(img_handle.read()).decode("utf-8")
    return encoded_img


def pformat(data: dict, prefix: str = "") -> str:
    """Prints a dictonary as a formatted yaml string."""
    yaml_string = yaml.dump(data, sort_keys=False, default_flow_style=False)
    fomatted_string = f"{prefix}{yaml_string}"
    return fomatted_string


def configure_logging(level: Optional[int] = logging.INFO) -> None:
    """Sets up the default logger."""
    logging.basicConfig(level=level, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)