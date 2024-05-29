import requests
import json
from requests_toolbelt import MultipartEncoder
import os
from typing import Dict, List, Tuple
from pathlib import Path

from archetypeai.common import DEFAULT_ENDPOINT, safely_extract_response_data
from archetypeai._base import ApiBase
from archetypeai._files import FilesApi
from archetypeai._capabilities import CapabilitiesApi
from archetypeai._data_processing import DataProcessingApi


class ArchetypeAI(ApiBase):
    """Main client for the Archetype AI platform."""

    files: FilesApi
    capabilities: CapabilitiesApi
    data_processing: DataProcessingApi

    def __init__(self, api_key: str, api_endpoint: str = DEFAULT_ENDPOINT) -> None:
        super().__init__(api_key, api_endpoint)
        self.files = FilesApi(api_key, api_endpoint)
        self.capabilities = CapabilitiesApi(api_key, api_endpoint)
        self.data_processing = DataProcessingApi(api_key, api_endpoint)

    ##### EVERYTHING BELOW IS LEGACY AND NEEDS REFACTORED!!! ####

    def datasets_create(self, dataset_config: dict) -> Tuple[int, Dict]:
        """TODO"""
        api_endpoint = os.path.join(self.api_endpoint, 'datasets/create')
        data_payload = {"dataset_config": dataset_config}
        response = requests.post(api_endpoint, data=json.dumps(data_payload), headers=self.auth_headers)
        return response.status_code, safely_extract_response_data(response)
    
    def datasets_modify(self, dataset_uid: str, modification_config: dict) -> Tuple[int, Dict]:
        """TODO"""
        api_endpoint = os.path.join(self.api_endpoint, 'datasets/modify')
        data_payload = {"dataset_uid": dataset_uid, "modification_config": modification_config}
        response = requests.post(api_endpoint, data=json.dumps(data_payload), headers=self.auth_headers)
        return response.status_code, safely_extract_response_data(response)

    def datasets_get_info(self, dataset_uid: str) -> Tuple[int, Dict]:
        """TODO"""
        api_endpoint = os.path.join(self.api_endpoint, 'datasets/info')
        response = requests.get(api_endpoint, params={"dataset_uid": dataset_uid}, headers=self.auth_headers)
        return response.status_code, safely_extract_response_data(response)

    def datasets_get_metadata(self, dataset_uid: str) -> Tuple[int, Dict]:
        """TODO"""
        api_endpoint = os.path.join(self.api_endpoint, 'datasets/metadata')
        response = requests.get(api_endpoint, params={"dataset_uid": dataset_uid}, headers=self.auth_headers)
        return response.status_code, safely_extract_response_data(response)