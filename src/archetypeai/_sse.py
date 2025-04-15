from typing import Callable
import json
import logging
from queue import Queue
import threading
import time

from sseclient import SSEClient
import requests


class ServerSideEventsReader:
    """Manages a threaded SSE reader."""

    heartbeat_sec: int = 30
    continue_worker_loop: bool = False
    read_event_queue: Queue = Queue()

    def __init__(self, session_endpoint: str, header: dict):
        self.worker = threading.Thread(
            target=self._worker, args=(session_endpoint, header))
        self.worker.start()

    def __del__(self):
        self.close()

    def close(self) -> bool:
        """Stops and closes an active reader."""
        worker_stopped = False
        self.continue_worker_loop = False
        if self.worker is not None:
            self.worker.join()
            self.worker = None
            worker_stopped = True
        return worker_stopped

    def read(self, max_num_events: int = -1):
        """Reads any queued events."""
        num_events_read = 0
        while not self.read_event_queue.empty():
            event = self.read_event_queue.get()
            yield event
            num_events_read += 1
            if max_num_events > 0 and num_events_read >= max_num_events:
                break
    
    def _worker(self, session_endpoint: str, header: dict):
        self.continue_worker_loop = True
        last_event_id = None
        restart_delay_sec = 1
        while self.continue_worker_loop:
            try:
                last_event_id = self._run_worker_loop(session_endpoint, header, last_event_id)
            except Exception as exception:
                logging.exception("Failed to run reader loop - restarting...")
                time.sleep(restart_delay_sec)
                restart_delay_sec *= 2

    def _run_worker_loop(self, session_endpoint: str, header: dict, last_event_id: int) -> int:

        logging.info(f"[sse reader] Connecting to {session_endpoint}")
        sse_event_reader = SSEClient(session_endpoint, headers=header, last_id=last_event_id)
    
        start_time = time.time()
        num_events_read = 0
        while self.continue_worker_loop:
            # Try and read any SSE events, this will block until an event is received.
            for event in sse_event_reader:
                last_event_id = event.id
                event_data = json.loads(event.data)
                self.read_event_queue.put(event_data)
                num_events_read += 1

                assert "type" in event_data
                if event_data["type"] == "sse.stream.heartbeat":
                    # Break from the reader loop to check to ensure the worker is still alive.
                    break
                if event_data["type"] == "sse.stream.end":
                    # Cancel the worker loop so the thread will gracefully stop.
                    self.continue_worker_loop = False
                    break

        current_time = time.time()
        run_time = current_time - start_time
        logging.info(f"[sse reader] Reached end of stream. num_events: {num_events_read} run_time: {run_time:.2f} sec")

        return last_event_id