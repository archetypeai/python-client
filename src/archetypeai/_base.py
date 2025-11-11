from typing import Dict, List, Tuple, Optional

import logging
from pathlib import Path
import sys
import secrets

import requests

from archetypeai._common import DEFAULT_ENDPOINT, safely_extract_response_data


class ApiBase:
    """Base API functionality shared across all API modules."""

    def __init__(self,
                 api_key: str,
                 api_endpoint: str = DEFAULT_ENDPOINT,
                 num_retries: int = 3,
                 log_level: int = logging.INFO,
                 log_format: str = "[%(asctime)s] %(message)s",
                 client_id: str = "",
                 request_timeout_sec: Optional[int] = None,
                 ) -> None:
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.auth_headers = {"Authorization": f"Bearer {self.api_key}"}
        self.num_retries = num_retries
        self.valid_response_codes = (200, 201)
        self.client_id = client_id if client_id else secrets.token_hex(8)  # Generate a uid for this client.
        self.request_timeout_sec = request_timeout_sec
        logging.basicConfig(level=log_level, format=log_format, datefmt="%H:%M:%S", stream=sys.stdout)
    
    def requests_get(self, api_endpoint: str, params: dict = {}, additional_headers: dict = {}) -> dict:
        request_args = {"api_endpoint": api_endpoint, "params": params, "additional_headers": additional_headers}
        return self._execute_request(request_func=self._requests_get, request_args=request_args)

    def _requests_get(self, api_endpoint: str, params: dict = {}, additional_headers: dict = {}) -> Tuple[int, dict]:
        response = requests.get(api_endpoint, params=params, headers={**self.auth_headers, **additional_headers})
        return response.status_code, safely_extract_response_data(response)
    
    def requests_post(self, api_endpoint: str, data_payload: bytes, additional_headers: dict = {}) -> dict:
        request_args = {"api_endpoint": api_endpoint, "data_payload": data_payload, "additional_headers": additional_headers}
        return self._execute_request(request_func=self._requests_post, request_args=request_args)

    def _requests_post(self, api_endpoint: str, data_payload: bytes, additional_headers: dict = {}) -> Tuple[int, dict]:
        response = requests.post(
            api_endpoint,
            data=data_payload,
            headers={**self.auth_headers, **additional_headers},
            timeout=self.request_timeout_sec)
        return response.status_code, safely_extract_response_data(response)

    def requests_delete(self, api_endpoint: str, params: dict = {}, additional_headers: dict = {}) -> dict:
        request_args = {"api_endpoint": api_endpoint, "params": params, "additional_headers": additional_headers}
        return self._execute_request(request_func=self._requests_delete, request_args=request_args)

    def _requests_delete(self, api_endpoint: str, params: dict = {}, additional_headers: dict = {}) -> Tuple[int, dict]:
        response = requests.delete(api_endpoint, params=params, headers={**self.auth_headers, **additional_headers})
        return response.status_code, safely_extract_response_data(response)

    def requests_download(self, api_endpoint: str, params: dict = {}, additional_headers: dict = {}) -> dict:
        request_args = {"api_endpoint": api_endpoint, "params": params, "additional_headers": additional_headers}
        return self._execute_request(request_func=self._requests_download, request_args=request_args)

    def _requests_download(self, api_endpoint: str, params: dict = {}, additional_headers: dict = {}) -> Tuple[int, requests.Response]:
        response = requests.get(
            api_endpoint,
            params=params,
            headers={**self.auth_headers, **additional_headers},
            timeout=self.request_timeout_sec)
        if response.status_code != 200:
            logging.warning(f"Failed to download file: {api_endpoint}. Error: {response}")
        return response.status_code, response

    def _execute_request(self, request_func, request_args: dict):
        num_attempts = 0
        while num_attempts < self.num_retries:
            response_code, response_data = request_func(**request_args)
            if response_code in self.valid_response_codes:
                return response_data
            logging.info(f"Failed to get valid response, got {response_code} {response_data} retrying...")
            num_attempts += 1
            if num_attempts >= self.num_retries:
                error_msg = f"Request failed after {num_attempts} attempts with error: {response_code} {response_data}"
                raise ValueError(error_msg)
    
    def _get_endpoint(self, base_endpoint: str, *args) -> str:
        subpath = None
        for arg in args:
            if subpath is None:
                subpath = arg
            else:
                subpath = Path(subpath) / Path(arg)
        protocol= ""
        potential_protocols = ("https://", "http://", "wss://", "ws://")
        for potential_protocol in potential_protocols:
            if base_endpoint.startswith(potential_protocol):
                protocol = potential_protocol
                break
        api_endpoint = protocol + str(Path(base_endpoint.replace(protocol, "")) / Path(subpath))
        api_endpoint = api_endpoint.replace("\\", "/")  # Needed for Windows style joins.
        return api_endpoint

    def get_file_type(self, filename: str) -> str:
        """Returns the file type of the input filename or raises an error."""
        file_ext = Path(filename).suffix.lower()
        file_ext_mapper = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.mp4': 'video/mp4',
            '.json': 'text/plain',
            '.jsonl': 'text/plain',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.text': 'text/plain',
        }
        if file_ext in file_ext_mapper:
            return file_ext_mapper[file_ext]
        raise ValueError(f"Unsupported file type: {file_ext}")

    def get_client_id(self) -> str:
        return self.client_id