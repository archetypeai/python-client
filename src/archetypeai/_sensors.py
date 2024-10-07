from typing import Any
import logging
import json

from archetypeai._base import ApiBase
from archetypeai._socket_manager import SocketManager


class SensorsApi(ApiBase):
    """Main sensor client for streaming data to the Archetype AI platform."""

    def __init__(self, api_key: str, api_endpoint: str, num_sensor_threads: int = 1) -> None:
        super().__init__(api_key, api_endpoint)
        self.num_sensor_threads = num_sensor_threads
        self.streamer = None
        self.subscribers = []
    
    def register(self, sensor_name: str, sensor_metadata: dict = {}, topic_ids: list[str] = []) -> bool:
        """Registers a sensor with the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "sensors", "register")
        data_payload = {"sensor_name": sensor_name, "sensor_metadata": sensor_metadata, "topic_ids": topic_ids}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        logging.info(f"Successfully registered sensor {sensor_name} stream_uid: {response['stream_uid']}")
        self.streamer = SocketManager(self.api_key, self.api_endpoint, num_worker_threads=self.num_sensor_threads)
        self.streamer._start_stream(response["stream_uid"], response["sensor_endpoint"], "sensors/streamer")
        return True
    
    def subscribe(self, sensor_name: str, topic_ids: list[str] = []) -> bool:
        """Subscribes to a sensor stream from the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "sensors", "subscribe")
        data_payload = {"sensor_name": sensor_name, "topic_ids": topic_ids}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        logging.info(f"Successfully subscribed to sensor {sensor_name} subscriber_uid: {response['subscriber_uid']}")
        subscriber = SocketManager(self.api_key, self.api_endpoint, num_worker_threads=self.num_sensor_threads)
        subscriber._start_stream(response["subscriber_uid"], response["subscriber_endpoint"], "sensors/subscriber")
        self.subscribers.append(subscriber)
        return True

    def send(self, topic_id: str, data: Any, timestamp: float = -1.0) -> bool:
        assert self.streamer is not None, "Sensor not registered. Call register first."
        return self.streamer.send(topic_id, data, timestamp)

    def close(self) -> bool:
        if self.streamer:
            self.streamer.close()
        for subscriber in self.subscribers:
            subscriber.close()
        return True 

    def get_stats(self):
        if self.streamer:
            return self.streamer.get_stats()
        return {}

    def get_sensor_data(self) -> list[dict]:
        events = []
        for subscriber in self.subscribers:
            for sensor_name, topic_id, data in subscriber.get_data():
                events.append({"sensor_name": sensor_name, "topic_id": topic_id, "data": data})
        return events