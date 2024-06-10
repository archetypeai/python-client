import json

from archetypeai._base import ApiBase


class DataProcessingApi(ApiBase):
    """Main class for handling all data processing API calls."""

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)

    def create_job(self, job_config: dict) -> dict:
        """Creates a new data processing job."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "data_processing")
        data_payload = {"job_config": job_config}
        response_data = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        return response_data
    
    def get_info(self) -> dict:
        """Returns the high-level information about all data processing jobs in your organization."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "data_processing/info")
        response_data = self.requests_get(api_endpoint)
        return response_data

    def get_metadata(self, shard_index: int = -1, max_items_per_shard: int = -1) -> dict:
        """Gets a list of metadata about any data processing jobs in your organization.

        Use the shard_index and max_items_per_shard to retrieve information about a subset of jobs.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "data_processing/metadata")
        params = {"shard_index": shard_index, "max_items_per_shard": max_items_per_shard}
        return self.requests_get(api_endpoint, params=params)