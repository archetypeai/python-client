from typing import Any
import json

from archetypeai._base import ApiBase


class MessagingApi(ApiBase):
    """Main class for handling all messaging API calls."""

    def __init__(self, api_key: str, api_endpoint: str, client_name: str = "python_client") -> None:
        super().__init__(api_key, api_endpoint)
        self.client_name = client_name
        self.subscriber_info = []
    
    def subscribe(self, topic_ids: list[str]) -> dict:
        assert topic_ids, "Failed to subscribe, topic ids is empty!"
        api_endpoint = self._get_endpoint(self.api_endpoint, "messaging/subscribe")
        data_payload = {"client_name": self.client_name, "topic_ids": topic_ids}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        self.subscriber_info.append(response)
        return response

    def broadcast(self, topic_id: str, message: Any) -> dict:
        assert topic_id, "Failed to broadcast message, topic id is empty!"
        api_endpoint = self._get_endpoint(self.api_endpoint, "messaging/broadcast")
        data_payload = {"client_name": self.client_name, "messages": [{"topic_id": topic_id, "message": message}]}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        return response
    
    def get_next_messages(self) -> list[dict]:
        messages = []
        for subscriber_info in self.subscriber_info:
            subscriber_uid = subscriber_info["subscriber_uid"]
            api_endpoint = self._get_endpoint(self.api_endpoint, "messaging/retrieve")
            response = self.requests_get(api_endpoint, params={"subscriber_uid": subscriber_uid})
            if response:
                messages.extend(response)
        return messages