from archetypeai.__init__ import __version__
from archetypeai._base import ApiBase
from archetypeai._capabilities import CapabilitiesApi
from archetypeai._common import DEFAULT_ENDPOINT, filter_kwargs
from archetypeai._files import FilesApi
from archetypeai._messaging import MessagingApi
from archetypeai._sensors import SensorsApi
from archetypeai._lens import LensApi
from archetypeai._kafka_client import KafkaApi


class ArchetypeAI(ApiBase):
    """Main client for the Archetype AI platform."""

    files: FilesApi
    capabilities: CapabilitiesApi
    messaging: MessagingApi
    sensors: SensorsApi
    lens: LensApi
    kafka: KafkaApi

    @staticmethod
    def get_version() -> str:
        """Returns the current version of the Archetype client."""
        return __version__
    
    @staticmethod
    def get_default_endpoint() -> str:
        """Returns the default endpoint the Archetype client should connect to."""
        return DEFAULT_ENDPOINT

    def __init__(self, api_key: str, api_endpoint: str = DEFAULT_ENDPOINT, **kwargs) -> None:
        super().__init__(api_key, api_endpoint)
        input_args = {"api_key": api_key, "api_endpoint": api_endpoint, **kwargs}
        self.files = FilesApi(**filter_kwargs(FilesApi.__init__, input_args))
        self.capabilities = CapabilitiesApi(**filter_kwargs(CapabilitiesApi.__init__, input_args))
        self.messaging = MessagingApi(**filter_kwargs(MessagingApi.__init__, input_args))
        self.sensors = SensorsApi(**filter_kwargs(SensorsApi.__init__, input_args))
        self.lens = LensApi(**filter_kwargs(LensApi.__init__, input_args))
        self.kafka = KafkaApi(**filter_kwargs(KafkaApi.__init__, input_args))