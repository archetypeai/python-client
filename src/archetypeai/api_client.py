import requests
import json
from requests_toolbelt import MultipartEncoder
import os
from typing import Dict, List, Tuple
from pathlib import Path

_DEFAULT_ENDPOINT = 'https://api.archetypeai.dev/v0.3'


class ArchetypeAI:
    """Main client for the Archetype AI platform."""

    def __init__(self, api_key: str, api_endpoint: str = _DEFAULT_ENDPOINT) -> None:
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.auth_headers = {"Authorization": f"Bearer {self.api_key}"}
    
    def upload(self, filename: str) -> Tuple[int, Dict]:
        """Uploads a local or s3 file to the Archetype AI platform."""
        is_s3_file = filename.startswith('s3://')
        if is_s3_file:
            return _upload_s3_file(filename, self.api_endpoint, self.auth_headers)
        else:
            return _upload_local_file(filename, self.api_endpoint, self.auth_headers)

    def summarize(self, query: str, file_ids: List[str]) -> Tuple[int, Dict]:
        """Runs the summarization API on the list of file IDs."""
        api_endpoint = os.path.join(self.api_endpoint, 'summarize')
        data_payload = {'query': query, 'file_ids': file_ids}
        response = requests.post(api_endpoint, data=json.dumps(data_payload), headers=self.auth_headers)
        return response.status_code, _safely_extract_response_data(response)

    def describe(self, query: str, file_ids: List[str]) -> Tuple[int, Dict]:
        """Runs the description API on the list of file IDs."""
        api_endpoint = os.path.join(self.api_endpoint, 'describe')
        data_payload = {'query': query, 'file_ids': file_ids}
        response = requests.post(api_endpoint, data=json.dumps(data_payload), headers=self.auth_headers)
        return response.status_code, _safely_extract_response_data(response)


def _upload_local_file(filename: str, api_endpoint: str, auth_headers: Dict) -> Tuple[int, Dict]:
    """Uploads a local file to the Archetype AI platform."""
    api_endpoint = os.path.join(api_endpoint, 'files')
    with open(filename, 'rb') as file_handle:
        encoder = MultipartEncoder(
            {'file': (os.path.basename(filename), file_handle.read(), _get_file_type(filename))})
        response = requests.post(
            api_endpoint, data=encoder, headers={**auth_headers, 'Content-Type': encoder.content_type})
        return response.status_code, _safely_extract_response_data(response)


def _upload_s3_file(filename: str, api_endpoint: str, auth_headers: Dict) -> Tuple[int, Dict]:
    """Uploads a remote s3 file to the Archetype AI platform."""
    api_endpoint = os.path.join(api_endpoint, 'files/s3')
    data_payload = {'filenames': [filename]}
    response = requests.post(api_endpoint, data=json.dumps(data_payload), headers=auth_headers)
    return response.status_code, _safely_extract_response_data(response)


def _get_file_type(filename: str) -> str:
    """Returns the file type of the input filename."""
    file_ext = Path(filename).suffix.lower()
    file_ext_mapper = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.mp4': 'video/mp4',
        '.json': 'plain/text',
        '.csv': 'plain/text',
        '.text': 'plain/text',
    }
    if file_ext in file_ext_mapper:
        return file_ext_mapper[file_ext]
    raise ValueError(f"Unsupported file type: {file_ext}")


def _safely_extract_response_data(response: requests.Response) -> Dict:
    """Safely extracts the response data from both valid and invalid responses."""
    try:
        response_data = response.json()
        return response_data
    except:
        return {}