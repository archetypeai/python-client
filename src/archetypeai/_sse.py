from typing import Callable
import json
import logging
from queue import Queue
import threading
import time
import ast

from sseclient import SSEClient
import requests


class ServerSideEventsReader:
    """Manages a threaded SSE reader."""

    def __init__(self, session_endpoint: str, header: dict, max_read_time_sec: float = -1.0):
        self.max_read_time_sec = max_read_time_sec
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
    
    def _worker(self, session_endpoint: str, header: dict):
        self.continue_worker_loop = True
        restart_delay_sec = 1
        start_time = time.time()
        last_event_id = None
        while self.continue_worker_loop:
            try:
                last_event_id = self._run_worker_loop(session_endpoint, header, start_time, last_event_id)
            except Exception as exception:
                logging.exception("Failed to run reader loop - restarting...")
                time.sleep(restart_delay_sec)
                restart_delay_sec = max(restart_delay_sec * 2, 10)
        self.continue_worker_loop = False
        self.worker = None

    def _run_worker_loop(self, session_endpoint: str, header: dict, start_time: float, last_event_id: int) -> int:

        logging.info(f"[sse reader] Connecting to {session_endpoint}")
        sse_event_reader = SSEClient(session_endpoint, headers=header, last_id=last_event_id)
    
        num_events_read = 0
        while self.continue_worker_loop:
            # Try and read any SSE events, this will block until an event is received.
            for event in sse_event_reader:
                last_event_id = event.id
                try:
                    # The SSE stream encodes JSON data as utf-8 binary data which is then packed
                    # into a standard string along with the SSE protocol headers. To decode the
                    # data, we need to strip the binary and single-quote identifiers to get back
                    # a cleaned string and then convert that to json.
                    raw_data = event.data
                    # assert raw_data.startswith("b'")
                    # assert raw_data.endswith("'")
                    # # Remove the outer binary and single quote tags.
                    # json_content = str(raw_data[1:]).replace("'", "") 
                    event_data = json.loads(raw_data)

                    assert "type" in event_data
                    self.read_event_queue.put(event_data)
                    num_events_read += 1
                    if event_data["type"] == "sse.stream.heartbeat":
                        # Break from the reader loop to check to ensure the worker is still alive.
                        break
                    if event_data["type"] == "sse.stream.end":
                        # Cancel the worker loop so the thread will gracefully stop.
                        self.continue_worker_loop = False
                        break
                    if self.max_read_time_sec >= 0 and time.time() - start_time >= self.max_read_time_sec:
                        self.continue_worker_loop = False
                        break
                except Exception as exception:
                    logging.exception(f"Failed to parse JSON packet: {raw_data}")
                

        current_time = time.time()
        run_time = current_time - start_time
        logging.info(f"[sse reader] Reached end of stream. num_events: {num_events_read} run_time: {run_time:.2f} sec")

        return last_event_id