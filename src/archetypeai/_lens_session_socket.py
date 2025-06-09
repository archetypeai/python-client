import json
import logging
from queue import Queue
import threading
import time

import websocket


class LensSessionSocket:
    """Manages websocket connections for each lens session."""

    def __init__(self, session_endpoint: str, header: dict):
        self.heartbeat_sec = 30
        self.max_worker_restarts = 10
        self.run_worker = False
        self.read_event_queue = Queue()
        self.write_event_queue = Queue()
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
        num_restarts = 0
        if "User-Agent" not in header:
            header["User-Agent"] = "archetypeai.py"
        while self.run_worker:
            try:
                self.run_worker = self._run_worker_loop(session_endpoint, header)
            except Exception as exception:
                num_restarts += 1
                if num_restarts < self.max_worker_restarts:
                    logging.exception("Failed to run socket loop - restarting...")
                else:
                    logging.exception("Failed to run socket loop...")
                    self.run_worker = False
        self.run_worker = False

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
                if event_data:
                    self.read_event_queue.put(event_data)
                else:
                    logging.warning(f"Received empty event: {event_data}")
            else:
                time.sleep(0.1)
            # Send a periodic heartbeat to keep the connection alive.
            if current_time - last_event >= self.heartbeat_sec:
                self.write_event_queue.put({"type": "session.heartbeat"})
        return self.run_worker