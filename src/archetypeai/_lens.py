from typing import Callable
import json
import logging
import time

import yaml

from archetypeai._base import ApiBase
from archetypeai._lens_session_socket import LensSessionSocket
from archetypeai._sse import ServerSideEventsReader


class SessionsApi(ApiBase):
    """Main class for handling all lens session API calls."""

    session_socket_cache: dict = {}

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)

    def __del__(self):
        self.close()

    def get_info(self) -> dict:
        """Gets the high-level info for all lens sessions across your org."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/sessions/info")
        return self.requests_get(api_endpoint)

    def get_metadata(self, shard_index: int = -1, max_items_per_shard: int = -1, session_id: str = "") -> dict:
        """Gets a list of metadata about any lens sessions across your org.

        Use the shard_index and max_items_per_shard to retrieve information about a subset of sessions.

        To request metadata about a specific session, pass just the session_id.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/sessions/metadata")
        params = {"shard_index": shard_index, "max_items_per_shard": max_items_per_shard, "session_id": session_id}
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
            socket = LensSessionSocket(session_endpoint, {"Authorization":f"Bearer {self.api_key}"})
            self.session_socket_cache[session_id] = socket
        except Exception as exception:
            logging.exception(f"Failed to connect to session at {session_endpoint}")
            return False
        return True
    
    def read(self, session_id: str, client_id: str = "") -> list[dict]:
        """Reads an event from an open session and returns the response."""
        assert session_id in self.session_socket_cache, f"Unknown session ID {session_id}"
        client_id = client_id if client_id else self.client_id
        event_data = {"type": "session.read", "event_data": {"client_id": client_id}}
        response = self.write(session_id, event_data)
        return response
    
    def write(self, session_id: str, event_data: dict) -> dict:
        """Writes an event to an open session and returns the response."""
        assert session_id in self.session_socket_cache, f"Unknown session ID {session_id}"
        response = self.session_socket_cache[session_id].send_and_recv(event_data)
        return response

    def process_event(self, session_id: str, event: dict) -> dict:
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/sessions/events/process")
        data = {"session_id": session_id, "event": event}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data))
        return response

    def create_sse_consumer(self, session_id: str, max_read_time_sec: float = -1.0) -> ServerSideEventsReader:
        """Creates a new server-side-event consumer and starts it in a background thread."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"lens/sessions/consumer/{session_id}")
        headers = {"Authorization":f"Bearer {self.api_key}"}
        sse_consumer = ServerSideEventsReader(api_endpoint, headers, max_read_time_sec)
        return sse_consumer
    
    def close(self) -> bool:
        """Closes and removes any open session socket. Returns true if any sessions were closed, false otherwise."""
        sessions_closed = False
        if self.session_socket_cache:
            for session_id in self.session_socket_cache:
                self.session_socket_cache[session_id].close()
            self.session_socket_cache = {}
            sessions_closed = True
        return sessions_closed 


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

        To request metadata about a specific lens, pass just the lens_id.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/metadata")
        params = {"shard_index": shard_index, "max_items_per_shard": max_items_per_shard, "lens_id": lens_id}
        return self.requests_get(api_endpoint, params=params)

    def register(self, lens_config: dict) -> dict:
        """Registers a new lens with the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/register")
        data = {"lens_config": lens_config}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data))
        lens_id = response.get("lens_id", None)
        assert lens_id, f"Missing lens_id: {response}"
        return response

    def clone(self, lens_id: str) -> dict:
        """Clones an existing lens to create a new custom lens."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/clone")
        data = {"lens_id": lens_id}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data))
        lens_id = response.get("lens_id", None)
        assert lens_id, f"Missing lens_id: {response}"
        return response

    def modify(self, lens_id: str, lens_params: dict) -> dict:
        """Modifies an existing lens and returns the results."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/modify")
        data = {"lens_id": lens_id, **lens_params}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data))
        return response

    def delete(self, lens_id: str) -> dict:
        """Deletes an existing lens and returns the results."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "lens/delete")
        data = {"lens_id": lens_id}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data))
        return response

    def create_and_run_lens(
        self,
        lens_config: str | dict,
        session_fn: Callable,
        auto_destroy_lens: bool = True,
        auto_destroy_session: bool = True,
        **session_kwargs
        ):
        """Creates a new lens and automatically launches a new lens session."""

        # If the lens is passed as a str then dynamically convert it to a dict.
        if isinstance(lens_config, str):
            lens_config = yaml.safe_load(lens_config)
        assert isinstance(lens_config, dict), f"Invalid input: {lens_config}"

        # Register the custom lens with the Archetype AI platform.
        lens_metadata = self.register(lens_config)
        assert "lens_id" in lens_metadata, f"Missing lens id: {lens_metadata}"
        lens_id = lens_metadata["lens_id"]

        fn_response = self.create_and_run_session(
            lens_id, session_fn, auto_destroy=auto_destroy_session, **session_kwargs)

        if auto_destroy_lens:
            # Delete the custom lens to clean things up.
            self.delete(lens_id)

        return fn_response

    def create_and_run_session(
        self,
        lens_id: str,
        session_fn: Callable,
        auto_destroy: bool = True,
        **session_kwargs
        ):
        """Creates and runs a lens session based on a pre-existing lens."""
        # Create a new session based on this lens.
        session_id, session_endpoint = self.create_session(lens_id)

        fn_response = None
        try:
            # Connect to the lens and run the custom session.
            fn_response = session_fn(session_id, session_endpoint, **session_kwargs)
        finally:
            if auto_destroy:
                # Clean up the lens at the end of the session.
                self.destroy_lens_session(session_id)

        return fn_response

    def create_session(self, lens_id: str):
        """Creates a session and returns the session_id and session_endpoint."""
        try:
            logging.debug(f"Creating lens with id: {lens_id}")
            response = self.sessions.create(lens_id)
            logging.debug(f"{response}")
            if "errors" in response:
                raise ValueError(response["errors"])
        except ValueError as err:
            logging.exception(f"{err}")
            raise

        # Extract the session_id and endpoint.
        session_id = response["session_id"]
        session_endpoint = response["session_endpoint"]
        logging.info(f"Session ID: {session_id} @ {session_endpoint}")
        return session_id, session_endpoint

    def destroy_lens_session(self, session_id: str) -> None:
        """Cleanly stops and destroys an active session."""
        try:
            # Destroy any active sessions.
            response = self.sessions.destroy(session_id)
            logging.debug(response)
            logging.info(f"Session Status: {response['session_status']}")
        except:
            logging.exception("Failed to destroy sessions!")
        # Close any open sessions sockets.
        self.sessions.close()
