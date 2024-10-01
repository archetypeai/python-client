import logging
import json

from archetypeai._socket_manager import SocketManager


class SensorsApi(SocketManager):
    """Main sensor client for streaming data to the Archetype AI platform."""

    def __init__(self, api_key: str, api_endpoint: str, num_sensor_threads: int = 1) -> None:
        super().__init__(api_key, api_endpoint, num_worker_threads=num_sensor_threads)
    
    def register(self, sensor_name: str, sensor_metadata: dict = {}, topic_ids: list[str] = []) -> bool:
        """Registers a sensor with the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "sensors", "register")
        data_payload = {"sensor_name": sensor_name, "sensor_metadata": sensor_metadata, "topic_ids": topic_ids}
        response_data = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        logging.info(f"Successfully registered sensor {sensor_name} stream_uid: {response_data['stream_uid']}")
        return self._start_stream(response_data["stream_uid"], response_data["sensor_endpoint"], "sensors/streamer")
    
    def subscribe(self, sensor_name: str, topic_ids: list[str] = []) -> bool:
        """Subscribes to a sensor stream from the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "sensors", "subscribe")
        data_payload = {"sensor_name": sensor_name, "topic_ids": topic_ids}
        response_data = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        logging.info(f"Successfully subscribed to sensor {sensor_name} subscriber_uid: {response_data['subscriber_uid']}")
        return self._start_stream(response_data["subscriber_uid"], response_data["subscriber_endpoint"], "sensors/subscriber")