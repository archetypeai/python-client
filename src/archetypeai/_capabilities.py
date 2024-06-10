import json

from archetypeai._base import ApiBase


class CapabilitiesApi(ApiBase):
    """Main class for handling all capability API calls."""
    
    def summarize(self, query: str, file_ids: list[str]) -> dict:
        """Runs the summarization API on the list of file IDs."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "summarize")
        data_payload = {"query": query, "file_ids": file_ids}
        response_data = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        return response_data

    def describe(self, query: str, file_ids: list[str]) -> dict:
        """Runs the description API on the list of file IDs."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "describe")
        data_payload = {"query": query, "file_ids": file_ids}
        response_data = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        return response_data