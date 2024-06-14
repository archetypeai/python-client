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
from archetypeai._messaging import MessagingApi
from archetypeai._sensors import SensorsApi


class ArchetypeAI(ApiBase):
    """Main client for the Archetype AI platform."""

    files: FilesApi
    capabilities: CapabilitiesApi
    data_processing: DataProcessingApi
    messaging: MessagingApi
    sensors: SensorsApi

    def __init__(self, api_key: str, api_endpoint: str = DEFAULT_ENDPOINT, **kwargs) -> None:
        super().__init__(api_key, api_endpoint)
        self.files = FilesApi(api_key, api_endpoint)
        self.capabilities = CapabilitiesApi(api_key, api_endpoint)
        self.data_processing = DataProcessingApi(api_key, api_endpoint)
        self.messaging = MessagingApi(api_key, api_endpoint, **kwargs)
        self.sensors = SensorsApi(api_key, api_endpoint, **kwargs)