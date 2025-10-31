from typing import Callable
import json
import logging
from queue import Queue
import threading
import time
import ast

import httpx
from httpx_sse import connect_sse


class ServerSideEventsReader:
    """Manages a threaded SSE reader."""

    def __init__(self, session_endpoint: str, header: dict, max_read_time_sec: float = -1.0, max_retries: int = 3):
        self.max_read_time_sec = max_read_time_sec
        self.max_retries = max_retries
        self.heartbeat_sec = 30
        self.continue_worker_loop = False
        self.read_event_queue = Queue()
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
            self.continue_worker_loop = False
            self.worker.join()
            self.worker = None
            worker_stopped = True
        return worker_stopped

    def read(self, max_num_events: int = -1, block: bool = False):
        """Reads any queued events."""
        num_events_read = 0
        queue_not_empty = not self.read_event_queue.empty()
        keep_reading = True if block else queue_not_empty
        while keep_reading:
            if queue_not_empty or block:
                event = self.read_event_queue.get(block=block)
                yield event
                num_events_read += 1
            # Stop reading if we've reached the end of the events (in non-blocking mode)
            # or if we've reached the maximum number of events.
            queue_empty = not self.read_event_queue.empty()
            queue_not_empty = not queue_empty
            if queue_empty and not block:
                keep_reading = False
            if max_num_events > 0 and num_events_read >= max_num_events:
                keep_reading = False
            # Always stop the reader loop if the main worker loop has stopped.
            keep_reading &= self.continue_worker_loop
    
    def _worker(self, session_endpoint: str, header: dict) -> None:
        self.continue_worker_loop = True
        restart_delay_sec = 1
        num_retries = 0
        start_time = time.time()
        while self.continue_worker_loop:
            try:
                success = self._run_worker_loop(session_endpoint, header, start_time)
                if success:
                    num_retries = 0
            except Exception as exception:
                num_retries += 1
                if num_retries <= self.max_retries:
                    logging.exception("Failed to run reader loop - restarting...")
                    time.sleep(restart_delay_sec)
                    restart_delay_sec = max(restart_delay_sec * 2, 10)
                else:
                    logging.exception("Failed to run reader loop - reached max retries, stopping...")
                    self.continue_worker_loop = False
        self.continue_worker_loop = False
        self.worker = None

    def _run_worker_loop(self, session_endpoint: str, header: dict, start_time: float) -> bool:
        """Connects to and reads events from an SSE remote connection until instructed to stop."""
        logging.info(f"[sse reader] Connecting to {session_endpoint}")
        headers = {**header, "Accept": "text/event-stream"}
        num_events_read = 0
        with httpx.Client() as client:
            with connect_sse(client, "GET", session_endpoint, headers=headers, timeout=10.0) as event_source:
                # Try and read any SSE events, this will block until an event is received.
                for event in event_source.iter_sse():
                    assert event.event == "message", event
                    try:
                        logging.debug(event)
                        event_data = json.loads(event.data)

                        assert "type" in event_data, event
                        self.read_event_queue.put(event_data)
                        num_events_read += 1
                        if event_data["type"] == "sse.stream.heartbeat":
                            continue
                        if event_data["type"] == "sse.stream.end":
                            # Cancel the worker loop so the thread will gracefully stop.
                            self.continue_worker_loop = False
                            break
                        if self.max_read_time_sec >= 0 and time.time() - start_time >= self.max_read_time_sec:
                            self.continue_worker_loop = False
                            break
                    except Exception as exception:
                        logging.debug(f"Failed to parse JSON packet: {event}")

                    if not self.continue_worker_loop:
                        logging.info(f"[sse reader] Received stop signal...")
                        break

        current_time = time.time()
        run_time = current_time - start_time
        logging.info(f"[sse reader] Reached end of stream. num_events: {num_events_read} run_time: {run_time:.2f} sec")

        return True