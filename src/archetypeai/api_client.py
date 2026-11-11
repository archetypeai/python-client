import logging
import warnings

from archetypeai._agents import AgentsApi
from archetypeai._base import ApiBase
from archetypeai._common import DEFAULT_CLIENT, DEFAULT_ENDPOINT, filter_kwargs
from archetypeai._errors import ApiError as ApiError
from archetypeai._files import FilesApi
from archetypeai._lens import LensApi
from archetypeai._projects import ProjectsApi

_VERSION = "26.11.11.0"


class ArchetypeAI(ApiBase):
    """Main client for the Archetype AI platform."""

    files: FilesApi
    projects: ProjectsApi
    agents: AgentsApi

    @staticmethod
    def get_version() -> str:
        """Returns the current version of the Archetype client."""
        return _VERSION

    @staticmethod
    def get_default_endpoint() -> str:
        """Returns the default endpoint the Archetype client should connect to."""
        return DEFAULT_ENDPOINT

    def __init__(
        self, api_key: str, api_endpoint: str = DEFAULT_ENDPOINT, client: str = DEFAULT_CLIENT, **kwargs
    ) -> None:
        """Creates a client. Tools built on the SDK pass their own name as `client`, e.g. `agent_skills`."""
        super().__init__(api_key, api_endpoint, client=client)
        input_args = {"api_key": api_key, "api_endpoint": api_endpoint, "client": client, **kwargs}
        self.files = FilesApi(**filter_kwargs(FilesApi.__init__, input_args))
        self._lens = LensApi(**filter_kwargs(LensApi.__init__, input_args))
        self.projects = ProjectsApi(**filter_kwargs(ProjectsApi.__init__, input_args))
        self.agents = AgentsApi(**filter_kwargs(AgentsApi.__init__, input_args))

    @property
    def lens(self) -> LensApi:
        """Deprecated: the lens API is replaced by the agents API (`client.agents`)."""
        warnings.warn(
            "The lens API is deprecated and will be removed in a future release. Use client.agents instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self._lens
