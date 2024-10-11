from typing import Any
import logging
import json
import time

from archetypeai._base import ApiBase
from archetypeai._socket_manager import SocketManager


class MessagingApi(ApiBase):
    """Main class for handling all messaging API calls."""

    def __init__(
        self,
        api_key: str,
        api_endpoint: str,
        client_name: str = "python_client",
        rate_limiter_timeout_sec: float = 0.5,
        fetch_time_sec=1.0) -> None:
        super().__init__(api_key, api_endpoint)
        self.client_name = client_name
        self.rate_limiter_timeout_sec = rate_limiter_timeout_sec
        self.fetch_time_sec = fetch_time_sec
        self.last_get_time = 0.0
        self.subscriber_info = []
        self.subscribers = []
    
    def subscribe(self, topic_ids: list[str]) -> dict:
        assert topic_ids, "Failed to subscribe, topic ids is empty!"
        api_endpoint = self._get_endpoint(self.api_endpoint, "messaging/subscribe")
        data_payload = {"client_name": self.client_name, "topic_ids": topic_ids}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        self.subscriber_info.append(response)

        new_subscriber = SocketManager(
            self.api_key, self.api_endpoint, num_worker_threads=1, fetch_time_sec=self.fetch_time_sec)
        new_subscriber._start_stream(response["subscriber_uid"], response["subscriber_endpoint"], "messaging")
        self.subscribers.append(new_subscriber)
        return response
    
    def close(self):
        """Closes and destroys any active subscribers."""
        for subscriber in self.subscribers:
            subscriber.close()
        self.subscribers = []

    def broadcast(self, topic_id: str, message: Any) -> dict:
        assert topic_id, "Failed to broadcast message, topic id is empty!"
        api_endpoint = self._get_endpoint(self.api_endpoint, "messaging/broadcast")
        data_payload = {"client_name": self.client_name, "messages": [{"topic_id": topic_id, "message": message}]}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        return response
    
    def get_next_messages(self) -> list[dict]:
        messages = []
        for subscriber in self.subscribers:
            for topic_id, message in subscriber.get_messages():
                messages.append({"topic_id": topic_id, "message": message})
        return messages