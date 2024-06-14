import requests
from typing import Dict

DEFAULT_ENDPOINT = "https://staging.archetypeai.dev/v0.5"


def safely_extract_response_data(response: requests.Response) -> Dict:
    """Safely extracts the response data from both valid and invalid responses."""
    try:
        response_data = response.json()
        return response_data
    except:
        return {}