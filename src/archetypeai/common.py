import requests
from typing import Dict

DEFAULT_ENDPOINT = 'https://api.archetypeai.dev/v0.3'


def safely_extract_response_data(response: requests.Response) -> Dict:
    """Safely extracts the response data from both valid and invalid responses."""
    try:
        response_data = response.json()
        return response_data
    except:
        return {}