import requests
import json
from requests_toolbelt import MultipartEncoder
import os
from typing import Dict, List, Tuple
from pathlib import Path
import inspect

from archetypeai.common import DEFAULT_ENDPOINT, safely_extract_response_data
from archetypeai._base import ApiBase
from archetypeai._files import FilesApi
from archetypeai._capabilities import CapabilitiesApi
from archetypeai._data_processing import DataProcessingApi
from archetypeai._messaging import MessagingApi
from archetypeai._sensors import SensorsApi

def _filter_kwargs(func, kwarg_dict):
    """Filters kwargs based on the signature of the input function."""
    sign = set([val.name for val in inspect.signature(func).parameters.values()])
    filtered_dict = {key: kwarg_dict[key] for key in sign.intersection(kwarg_dict.keys())}
    return filtered_dict


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
        self.messaging = MessagingApi(api_key, api_endpoint, **_filter_kwargs(MessagingApi.__init__, kwargs))
        self.sensors = SensorsApi(api_key, api_endpoint, **_filter_kwargs(SensorsApi.__init__, kwargs))