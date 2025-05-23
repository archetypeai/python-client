import base64
import logging
import yaml


def base64_encode(filename: str) -> str:
    with open(filename, "rb") as img_handle:
        encoded_img = base64.b64encode(img_handle.read()).decode("utf-8")
    return encoded_img


def pformat(data: dict, prefix: str = "") -> str:
    """Prints a dictonary as a formatted yaml string."""
    yaml_string = yaml.dump(data, sort_keys=False, default_flow_style=False)
    fomatted_string = f"{prefix}{yaml_string}"
    return fomatted_string