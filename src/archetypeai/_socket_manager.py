import logging
import json
import time
from queue import Queue
from typing import Any
import threading

from websocket import create_connection

from archetypeai._base import ApiBase

_CTRL_MSG_HEADER = "cm"
_DATA_MSG_HEADER = "dm"
_HEADER_KEY = "h"
_HEARTBEAT_DELAY_SEC = 5.0


class SocketManager(ApiBase):
    """Helper class for communicating with the Archetype AI platform via websockets."""

    def __init__(self, api_key: str, api_endpoint: str, num_worker_threads: int = 1, fetch_time_sec=2.0) -> None:
        super().__init__(api_key, api_endpoint)
        self.stream_uid = None
        self.streamer_endpoint = None
        self.num_workers = num_worker_threads
        self.fetch_time_sec = fetch_time_sec
        self.connected = False
        self.streamer_sockets = []
        self.threads = {}
        self.post_connect_timeout_sec = 1
        self.incoming_data_queue = Queue()
        self.incoming_message_queue = Queue()
        self.outgoing_message_queue = Queue()
        self.stats_queue = Queue()
        self.message_id = 0
        self._run_worker_loop = False
        self.max_outgoing_message_queue_size = 0
        self.outgoing_message_latency_total = 0.0
        self.outgoing_message_count = 0
        self.stats = {}
        self.stats["num_data_packets_sent"] = 0
        self.stats["max_outgoing_message_queue_size"] = 0
        self.stats["outgoing_message_queue_latency"] = 0
        self.stats["outgoing_message_latency"] = 0
    
    def _start_stream(self, stream_uid: str, streamer_endpoint: str, streamer_channel: str) -> bool:
        """Starts a new stream with the Archetype AI platform."""
        self.stream_uid = stream_uid
        self.streamer_endpoint = streamer_endpoint
        self.streamer_channel = streamer_channel
        self.message_id = 0
        
        self._safely_stop_streams()
        assert self._handshake()
        for worker_id, streamer_socket in enumerate(self.streamer_sockets):
            self.threads[worker_id] = threading.Thread(target=self._worker, args=(worker_id, streamer_socket))
            self.threads[worker_id].start()

        self.connected = True
        return self.connected

    def _safely_stop_streams(self):
        self._run_worker_loop = False
        for worker_id in self.threads:
            self.threads[worker_id].join()
        self.threads = {}
        self.streamer_sockets = []
        self.connected = False

    def close(self, wait_on_pending_data: bool = True):
        """Closes the connection with the server."""
        if wait_on_pending_data:
            while not self.outgoing_message_queue.empty():
                logging.info(f"outgoing data queue size: {self.outgoing_message_queue.qsize()}")
                time.sleep(0.1)
        self._safely_stop_streams()

    def send(self, topic_id: str, data: Any, timestamp: float = -1.0) -> bool:
        """Sends data to the Archetype AI platform under the given topic_id."""
        assert self.connected, "Client not connected. Make sure the stream is open!"
        timestamp = timestamp if timestamp >= 0 else time.time()
        message = {
            "topic_id": topic_id,
            "data": data,
            "timestamp": timestamp,
            "message_id": self.message_id,
            "stream_uid": self.stream_uid
        }
        self.message_id += 1
        self.outgoing_message_queue.put({_HEADER_KEY: _DATA_MSG_HEADER, **message})
        self._refresh_stats()
        return True

    def get_messages(self) -> Any:
        """Gets any pending messages sent to the client."""
        assert self.connected, "Client not connected. Make sure the stream is open!"
        while not self.incoming_message_queue.empty():
            topic_id, data = self.incoming_message_queue.get()
            yield topic_id, data

    def get_data(self) -> Any:
        """Gets any pending data sent to the client."""
        assert self.connected, "Client not connected. Make sure the stream is open!"
        while not self.incoming_data_queue.empty():
            sensor_name, topic_id, data = self.incoming_data_queue.get()
            yield sensor_name, topic_id, data

    def get_incoming_data_queue_size(self) -> int:
        return self.incoming_data_queue.qsize()
    
    def get_incoming_message_queue_size(self) -> int:
        return self.incoming_message_queue.qsize()
    
    def get_outgoing_message_queue_size(self) -> int:
        return self.outgoing_message_queue.qsize()
    
    def get_max_outgoing_message_queue_size(self) -> int:
        return self.stats["max_outgoing_message_queue_size"]
    
    def get_outgoing_message_queue_latency(self) -> float:
        """Returns the latency of the latest outgoing message queue in seconds."""
        self._refresh_stats()
        return self.stats["outgoing_message_queue_latency"]
    
    def get_outgoing_message_latency(self) -> float:
        """Returns the average latency of outgoing data packets in seconds."""
        self._refresh_stats()
        return self.stats["outgoing_message_queue_latency"]
    
    def get_stats(self) -> dict:
        """Returns the stats of a sensor stream."""
        self._refresh_stats()
        return self.stats

    def _refresh_stats(self):
        while not self.stats_queue.empty():
            stats_event = self.stats_queue.get()
            if "outgoing_message_queue_latency" in stats_event:
                self.stats["outgoing_message_queue_latency"] = stats_event["outgoing_message_queue_latency"]
            elif "max_outgoing_message_queue_size" in stats_event:
                self.stats["max_outgoing_message_queue_size"] = max(
                    stats_event["max_outgoing_message_queue_size"], self.stats["max_outgoing_message_queue_size"])

    def _worker(self, worker_id: str, streamer_socket) -> None:
        logging.debug(f"Starting worker {worker_id}")
        self._run_worker_loop = True
        try:
            self._worker_loop(worker_id, streamer_socket)
        except:
            logging.exception(f"Main loop failed, closing socket!")
            # Remove this failed worker from the thread pool.
            del self.threads[worker_id]
            del streamer_socket
            # If this worker has stopped then make sure all workers stop.
            self._safely_stop_streams()
    
    def _worker_loop(self, worker_id: str, streamer_socket) -> None:
        heatbeat_message = {_HEADER_KEY: _CTRL_MSG_HEADER, "topic_id": "ctl_msg/heartbeat", "data": {}, "timestamp": 0}
        fetch_message = {_HEADER_KEY: _CTRL_MSG_HEADER, "topic_id": "ctl_msg/fetch", "data": {}, "timestamp": 0}
        max_outgoing_message_queue_size = 0
        while self._run_worker_loop:
            # Broadcast any outgoing messages.
            while not self.outgoing_message_queue.empty():
                time_now = time.time()
                max_outgoing_message_queue_size = max(self.outgoing_message_queue.qsize(), max_outgoing_message_queue_size)
                message = self.outgoing_message_queue.get()
                queue_delay_time = time_now - message["timestamp"]
                self.stats_queue.put({
                    "outgoing_message_queue_latency": queue_delay_time,
                    "max_outgoing_message_queue_size": max_outgoing_message_queue_size
                })
                
                if message[_HEADER_KEY] == _CTRL_MSG_HEADER:
                    message_sent = self._send_control_message(message, streamer_socket)
                elif message[_HEADER_KEY] == _DATA_MSG_HEADER:
                    message_sent = self._send_data_message(message, streamer_socket)
                assert message_sent

            # Queue a heartbeat or fetch message if needed.
            time_now = time.time()
            if self._run_worker_loop and time_now - heatbeat_message["timestamp"] >= _HEARTBEAT_DELAY_SEC:
                heatbeat_message["timestamp"] = time_now
                self.outgoing_message_queue.put({_HEADER_KEY: _CTRL_MSG_HEADER, **heatbeat_message})
            if self._run_worker_loop and time_now - fetch_message["timestamp"] >= self.fetch_time_sec:
                fetch_message["timestamp"] = time_now
                self.outgoing_message_queue.put({_HEADER_KEY: _CTRL_MSG_HEADER, **fetch_message})

    def _handshake(self) -> bool:
        api_endpoint = self._get_endpoint(self.streamer_endpoint, self.streamer_channel, self.stream_uid)
        logging.info(f"Connecting to {api_endpoint}")
        for worker_id in range(self.num_workers):
            self.streamer_sockets.append(create_connection(api_endpoint))
        if self.post_connect_timeout_sec > 0:
            time.sleep(self.post_connect_timeout_sec)
        # Send and receive a control message to validate the connection.
        message = {_HEADER_KEY: _CTRL_MSG_HEADER, "topic_id": "ctl_msg/handshake", "data": {}, "timestamp": time.time()}
        for worker_id, streamer_socket in enumerate(self.streamer_sockets):
            if not self._send_control_message(message, streamer_socket):
                raise ValueError(f"Failed to handshake for socket {worker_id}")
        return True

    def _send_control_message(self, message: dict, streamer_socket) -> bool:
        assert message[_HEADER_KEY] == _CTRL_MSG_HEADER
        # Send the control message.
        assert self._send_data(message, streamer_socket) > 0
        # Get the control response.
        response_bytes = streamer_socket.recv()
        if not response_bytes:
            return False
        response = json.loads(response_bytes)
        if "topic_id" in response:
            if response["topic_id"].startswith("ctl_msg/"):
                logging.debug(f"Got control message: {response['topic_id']}")
            else:
                self.incoming_message_queue.put((response["topic_id"], response["data"]))
        elif "messages" in response:
            for message in response["messages"]:
                self.incoming_message_queue.put((message["topic_id"], message["message"]))
        elif "sensor_data" in response:
            for event in response["sensor_data"]:
                self.incoming_data_queue.put((event["sensor_name"], event["topic_id"], event["data"]))
        return True

    def _send_data_message(self, message: dict, streamer_socket) -> bool:
        """Sends a data message to the server, does not wait for a response."""
        assert message[_HEADER_KEY] == _DATA_MSG_HEADER
        start_time = time.time()
        num_bytes_sent = self._send_data(message, streamer_socket)
        assert num_bytes_sent > 0, f"Failed to send message!"
        end_time = time.time()
        latency = end_time - start_time
        topic_id = message["topic_id"]
        logging.debug(f"Sent topic_id: {topic_id} payload size: {num_bytes_sent} bytes latency: {latency}")
        self.outgoing_message_latency_total += latency
        self.outgoing_message_count += 1
        return True

    def _send_data(self, message: dict, streamer_socket) -> int:
        message_bytes = json.dumps(message).encode()
        streamer_socket.send_binary(message_bytes)
        num_bytes_sent = len(message_bytes)
        return num_bytes_sent