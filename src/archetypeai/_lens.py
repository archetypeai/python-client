import json
import logging
import websocket

from archetypeai._base import ApiBase


class SessionsApi(ApiBase):
    """Main class for handling all lens session API calls."""

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)
        self.subscriber_cache = {}

    def get_info(self) -> dict:
        """Gets the high-level info for all lens sessions across your org."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/sessions/info")
        return self.requests_get(api_endpoint)

    def get_metadata(self, shard_index: int = -1, max_items_per_shard: int = -1) -> dict:
        """Gets a list of metadata about any lens sessions across your org.

        Use the shard_index and max_items_per_shard to retrieve information about a subset of sessions.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/sessions/metadata")
        params = {"shard_index": shard_index, "max_items_per_shard": max_items_per_shard}
        return self.requests_get(api_endpoint, params=params)

    def create(self, lens_id: str) -> dict:
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/sessions/create")
        data = {"lens_id": lens_id}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data))
        return response

    def destroy(self, session_id: str) -> dict:
        assert session_id, "Failed to destroy, session_id is empty!"
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/sessions/destroy")
        data = {"session_id": session_id}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data))
        return response

    def connect(self, session_id: str, session_endpoint: str) -> bool:
        try:
            socket = websocket.create_connection(
                session_endpoint, header={"Authorization":f"Bearer {self.api_key}"})
            self.subscriber_cache[session_id] = socket
        except Exception as exception:
            logging.exception(f"Failed to connect to session at {session_endpoint}")
            return False
        return True
    
    def read(self, session_id: str, client_id: str = "") -> list[dict]:
        """Reads an event from an open session and returns the response."""
        assert session_id in self.subscriber_cache, f"Unknown session ID {session_id}"
        client_id = client_id if client_id else self.client_id
        event_data = {"type": "session.read", "event_data": {"client_id": client_id}}
        response = self.write(session_id, event_data)
        return response
    
    def write(self, session_id: str, event_data: dict) -> dict:
        """Writes an event to an open session and returns the response."""
        assert session_id in self.subscriber_cache, f"Unknown session ID {session_id}"
        socket = self.subscriber_cache[session_id]
        socket.send_binary(json.dumps(event_data).encode())
        response = socket.recv()
        response = json.loads(response)
        return response


class LensApi(ApiBase):
    """Main class for handling all lens API calls."""

    sessions: SessionsApi

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)
        self.sessions = SessionsApi(api_key, api_endpoint)

    def get_info(self) -> dict:
        """Gets the high-level info for all lenses across your org."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/info")
        return self.requests_get(api_endpoint)

    def get_metadata(self, shard_index: int = -1, max_items_per_shard: int = -1, lens_id: str = "") -> dict:
        """Gets a list of metadata about any lenses across your org.

        Use the shard_index and max_items_per_shard to retrieve information about a subset of lenses.

        To request metadata about a specific lens, the lens_id.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/metadata")
        params = {"shard_index": shard_index, "max_items_per_shard": max_items_per_shard, "lens_id": lens_id}
        return self.requests_get(api_endpoint, params=params)