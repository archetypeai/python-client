from archetypeai.__init__ import __version__
from archetypeai._base import ApiBase
from archetypeai._capabilities import CapabilitiesApi
from archetypeai._common import DEFAULT_ENDPOINT, filter_kwargs
from archetypeai._files import FilesApi
from archetypeai._messaging import MessagingApi
from archetypeai._sensors import SensorsApi


class ArchetypeAI(ApiBase):
    """Main client for the Archetype AI platform."""

    files: FilesApi
    capabilities: CapabilitiesApi
    messaging: MessagingApi
    sensors: SensorsApi

    @staticmethod
    def get_version() -> str:
        """Returns the current version of the Archetype client."""
        return __version__

    def __init__(self, api_key: str, api_endpoint: str = DEFAULT_ENDPOINT, **kwargs) -> None:
        super().__init__(api_key, api_endpoint)
        self.files = FilesApi(api_key, api_endpoint, **filter_kwargs(FilesApi.__init__, kwargs))
        self.capabilities = CapabilitiesApi(api_key, api_endpoint, **filter_kwargs(CapabilitiesApi.__init__, kwargs))
        self.messaging = MessagingApi(api_key, api_endpoint, **filter_kwargs(MessagingApi.__init__, kwargs))
        self.sensors = SensorsApi(api_key, api_endpoint, **filter_kwargs(SensorsApi.__init__, kwargs))