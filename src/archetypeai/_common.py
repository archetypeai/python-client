from typing import Dict
import inspect

import requests

DEFAULT_ENDPOINT = "https://api.archetypeai.dev/v0.5"


def safely_extract_response_data(response: requests.Response) -> Dict:
    """Safely extracts the response data from both valid and invalid responses."""
    try:
        response_data = response.json()
        return response_data
    except:
        return {}


def filter_kwargs(func, kwarg_dict):
    """Filters kwargs based on the signature of the input function."""
    sign = set([val.name for val in inspect.signature(func).parameters.values()])
    filtered_dict = {key: kwarg_dict[key] for key in sign.intersection(kwarg_dict.keys())}
    return filtered_dict