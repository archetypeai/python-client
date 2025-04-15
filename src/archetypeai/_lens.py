from typing import Callable
import json
import logging
from queue import Queue
import threading
import time

import websocket

from archetypeai._base import ApiBase
from archetypeai._sse import ServerSideEventsReader


class LensSessionSocket:
    """Manages websocket connections for each lens session."""

    heartbeat_sec: int = 30
    run_worker: bool = False
    read_event_queue: Queue = Queue()
    write_event_queue: Queue = Queue()

    def __init__(self, session_endpoint: str, header: dict):
        self.worker = threading.Thread(
            target=self._worker, args=(session_endpoint, header))
        self.worker.start()

    def __del__(self):
        self.close()

    def close(self) -> bool:
        """Stops and closes an active socket."""
        worker_stopped = False
        if self.run_worker:
            self.run_worker = False
            self.worker.join()
            self.worker = None
            worker_stopped = True
        return worker_stopped

    def send_and_recv(self, event_data: dict) -> dict:
        """Writes an event to an open session and returns the response."""
        self.write_event_queue.put(event_data)
        response = self.read_event_queue.get()
        response = json.loads(response)
        return response
    
    def _worker(self, session_endpoint: str, header: dict):
        self.run_worker = True
        while self.run_worker:
            try:
                self.run_worker = self._run_worker_loop(session_endpoint, header)
            except Exception as exception:
                logging.exception("Failed to run socket loop - restarting...")

    def _run_worker_loop(self, session_endpoint: str, header: dict) -> bool:
        socket = websocket.create_connection(session_endpoint, header=header)
        start_time = time.time()
        last_event = time.time()
        while self.run_worker:
            current_time = time.time()
            run_time = current_time - start_time
            if not self.write_event_queue.empty():
                last_event = time.time()
                # Send the event to the server.
                event_data = self.write_event_queue.get()
                logging.debug(f"[{run_time:.2f}] Sending event w/ type: {event_data['type']}...")
                socket.send_binary(json.dumps(event_data).encode())
                # Read back the response.
                event_data = socket.recv()
                self.read_event_queue.put(event_data)
            else:
                time.sleep(0.1)
            # Send a periodic heartbeat to keep the connection alive.
            if current_time - last_event >= self.heartbeat_sec:
                self.write_event_queue.put({"type": "session.heartbeat"})
        return self.run_worker


class SessionsApi(ApiBase):
    """Main class for handling all lens session API calls."""

    session_socket_cache: dict = {}

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)

    def __del__(self):
        for session_id in self.session_socket_cache:
            self.session_socket_cache[session_id].close()
        self.session_socket_cache = {}

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

    def create_sse_consumer(self, session_id: str) -> ServerSideEventsReader:
        """Creates a new server-side-event consumer and starts it in a background thread."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"lens/sessions/consumer/{session_id}")
        headers = {"Authorization":f"Bearer {self.api_key}"}
        sse_consumer = ServerSideEventsReader(api_endpoint, headers)
        return sse_consumer


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

    def create_and_run_session(
        self,
        lens_id: str,
        session_fn: Callable,
        auto_destroy: bool = True,
        **session_kwargs
        ):
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
        response = self.sessions.destroy(session_id)
        logging.debug(response)
        logging.info(f"Session Status: {response['session_status']}")
