import logging
import json
import os
import time
from queue import Queue
from typing import Any
import threading

from websocket import create_connection

from archetypeai._base import ApiBase

_CTRL_MSG_HEADER = "cm"
_DATA_MSG_HEADER = "dm"
_HEADER_KEY = "h"
_HEARTBEAT_DELAY_SEC = 0.1


class SensorsApi(ApiBase):
    """Main sensor client for streaming data to the Archetype AI platform."""

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)
        self.stream_uid = None
        self.streamer_endpoint = None
        self.streamer_socket = None
        self.post_connect_timeout_sec = 1
        self.incoming_message_queue = Queue()
        self.outgoing_message_queue = Queue()
        self.data_queue = Queue()
        self._run_worker_loop = False
        self.thread = None
        self.max_outgoing_message_queue_size = 0
        self.outgoing_message_queue_latency = 0.0
        self.outgoing_message_latency_total = 0.0
        self.outgoing_message_count = 0
    
    def register(self, sensor_name: str, sensor_metadata: dict = {}, topic_ids: list[str] = []) -> bool:
        """Registers a sensor with the Archetype AI platform."""
        api_endpoint = os.path.join(self.api_endpoint, "sensors")
        data_payload = {"sensor_name": sensor_name, "sensor_metadata": sensor_metadata, "topic_ids": topic_ids}
        response_data = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        self.stream_uid = response_data["stream_uid"]
        self.streamer_endpoint = response_data["sensor_endpoint"]
        logging.debug(f"Successfully registered sensor {sensor_name} stream_uid: {self.stream_uid}")
        assert self._handshake()
        self.thread = threading.Thread(target=self._worker, args=())
        self.thread.start()
        return True

    def close(self, wait_on_pending_data: bool = True):
        """Closes the connection with the server."""
        if self._run_worker_loop:
            while wait_on_pending_data and not self.outgoing_message_queue.empty():
                time.sleep(0.1)
            self._run_worker_loop = False
            self.thread.join()

    def send(self, topic_id: str, data: Any, timestamp: float = -1.0) -> bool:
        """Sends data to the Archetype AI platform under the given topic_id."""
        assert self.streamer_socket is not None, "Client not connected. Make sure the stream is open!"
        timestamp = timestamp if timestamp >= 0 else time.time()
        message = {"topic_id": topic_id, "data": data, "timestamp": timestamp}
        self.outgoing_message_queue.put({_HEADER_KEY: _DATA_MSG_HEADER, **message})
        return True

    def get_messages(self) -> Any:
        """Gets any pending messages sent to the client."""
        while not self.incoming_message_queue.empty():
            topic_id, data = self.incoming_message_queue.get()
            yield topic_id, data
        return '', {}
    
    def get_incoming_message_queue_size(self) -> int:
        return self.incoming_message_queue.qsize()
    
    def get_outgoing_message_queue_size(self) -> int:
        return self.outgoing_message_queue.qsize()
    
    def get_max_outgoing_message_queue_size(self) -> int:
        return self.max_outgoing_message_queue_size
    
    def get_outgoing_message_queue_latency(self) -> float:
        """Returns the latency of the latest outgoing message queue in seconds."""
        return self.outgoing_message_queue_latency
    
    def get_outgoing_message_latency(self) -> float:
        """Returns the average latency of outgoing data packets in seconds."""
        if self.outgoing_message_count == 0:
            return 0.0
        message_latency = self.outgoing_message_latency_total / self.outgoing_message_count
        return message_latency
    
    def get_stats(self) -> dict:
        """Returns the stats of a sensor stream."""
        stats = {}
        stats["num_data_packets_sent"] = self.outgoing_message_count
        stats["max_outgoing_message_queue_size"] = self.get_max_outgoing_message_queue_size()
        stats["outgoing_message_queue_latency"] = self.get_outgoing_message_queue_latency()
        stats["outgoing_message_latency"] = self.get_outgoing_message_latency()
        return stats

    def _worker(self) -> None:
        self._run_worker_loop = True
        heatbeat_message = {_HEADER_KEY: _CTRL_MSG_HEADER, "topic_id": "ctl_msg/heartbeat", "data": {}, "timestamp": 0}
        while self._run_worker_loop:
            time_now = time.time()
            message_sent = False
            if self.outgoing_message_queue.empty():
                if time_now - heatbeat_message["timestamp"] >= _HEARTBEAT_DELAY_SEC:
                    heatbeat_message["timestamp"] = time_now
                    message_sent = self._send_control_message(heatbeat_message)
                    assert message_sent
                else:
                    time.sleep(0.1)
            else:
                self.max_outgoing_message_queue_size = max(self.outgoing_message_queue.qsize(), self.max_outgoing_message_queue_size)
                message = self.outgoing_message_queue.get()
                queue_delay_time = time_now - message["timestamp"]
                self.outgoing_message_queue_latency = queue_delay_time
                if message[_HEADER_KEY] == _CTRL_MSG_HEADER:
                    message_sent = self._send_control_message(message)
                if message[_HEADER_KEY] == _DATA_MSG_HEADER:
                    message_sent = self._send_data_message(message)
                assert message_sent
            if message_sent:
                # Any message acts as a general heartbeat.
                heatbeat_message["timestamp"] = time_now

    def _handshake(self) -> bool:
        api_endpoint = os.path.join(self.streamer_endpoint, "sensors", self.stream_uid)
        logging.debug(f"Connecting to {api_endpoint}")
        self.streamer_socket = create_connection(api_endpoint)
        if self.post_connect_timeout_sec > 0:
            time.sleep(self.post_connect_timeout_sec)
        # Send and receive a control message to validate the connection.
        message = {_HEADER_KEY: _CTRL_MSG_HEADER, "topic_id": "ctl_msg/handshake", "data": {}, "timestamp": time.time()}
        return self._send_control_message(message)

    def _send_control_message(self, message: dict) -> bool:
        assert self.streamer_socket is not None, "Client not connected. Make sure the stream is open!"
        assert message[_HEADER_KEY] == _CTRL_MSG_HEADER
        assert self._send_data(message) > 0
        response_bytes = self.streamer_socket.recv()
        # logging.info(f"control msg response: {response_bytes}")
        response = json.loads(response_bytes)
        if "topic_id" in response:
            if response["topic_id"].startswith("ctl_msg/"):
                logging.info(f"Got control message: {response['topic_id']}")
            else:
                self.incoming_message_queue.put((response["topic_id"], response["data"]))
        return True

    def _send_data_message(self, message: dict) -> bool:
        assert self.streamer_socket is not None, "Client not connected. Make sure the stream is open!"
        assert message[_HEADER_KEY] == _DATA_MSG_HEADER
        start_time = time.time()
        num_bytes_sent = self._send_data(message)
        assert num_bytes_sent > 0, f"Failed to send message!"
        logging.debug(f"Sent topic_id: {message['topic_id']} payload size: {num_bytes_sent} bytes")
        response = self.streamer_socket.recv()
        end_time = time.time()
        self.outgoing_message_latency_total += end_time - start_time
        self.outgoing_message_count += 1
        if response == "ack":
            return True
        logging.warning(f"Failed to receive ack! Got: {response}")
        return False

    def _send_data(self, message: dict) -> int:
        message_bytes = self._encode_data_to_send(message)
        self.streamer_socket.send_binary(message_bytes)
        num_bytes_sent = len(message_bytes)
        return num_bytes_sent
    
    def _encode_data_to_send(self, data: dict[str, Any]) -> bytes:
        return json.dumps(data).encode()