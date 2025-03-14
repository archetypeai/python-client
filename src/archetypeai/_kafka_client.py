import json

from kafka import KafkaConsumer
from kafka import KafkaProducer

from archetypeai._base import ApiBase


class KafkaMessageConsumer:
    """Wrapper class for consuming kafka messages from a secure topic_uid."""

    def __init__(
        self,
        kafka_broker_endpoints: list[str],
        topic_uid: str,
        auto_offset_reset: str,
        consumer_timeout_ms: int,
        consumer_message_batch_size: int,
    ) -> None:
        self.consumer = KafkaConsumer(
            topic_uid,
            bootstrap_servers=kafka_broker_endpoints,
            auto_offset_reset=auto_offset_reset,
            consumer_timeout_ms=consumer_timeout_ms,
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        self.consumer_message_batch_size = consumer_message_batch_size

    def __iter__(self):
        batch_size = self.consumer_message_batch_size
        for batch_index, message in enumerate(self.consumer):
            yield message
            if batch_size > 0 and batch_index >= batch_size:
                break


class KafkaMessageProducer:
    """Wrapper class for producing kafka messages under a secure topic_uid."""

    def __init__(self, kafka_broker_endpoints: list[str], topic_id_map: dict) -> None:
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_broker_endpoints,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        self.topic_id_map = topic_id_map

    def send(self, topic_id: str, value: dict) -> bool:
        assert topic_id in self.topic_id_map
        topic_uid = self.topic_id_map[topic_id]
        self.producer.send(topic_uid, value=value)
        return True

    def flush(self) -> bool:
        self.producer.flush()
        return True


class KafkaApi(ApiBase):
    """Main class for handling all kafka API calls."""

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)
    
    def create_topic(self, topic_id: str) -> dict:
        """Creates a new topic on the Archetype AI kafka service."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "kafka/topics/create")
        data_payload = {"topic_id": topic_id}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        return response

    def subscribe_topic(self, topic_id: str) -> dict:
        """Subscribes to an existing topic on the Archetype AI kafka service."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "kafka/topics/subscribe")
        data_payload = {"topic_id": topic_id}
        response = self.requests_post(api_endpoint, data_payload=json.dumps(data_payload))
        return response

    def create_producer(self, topic_ids: list[str]) -> KafkaMessageProducer:
        """Creates the topic_ids on the Archetype kafka service and returns a producer for them."""
        assert topic_ids, "Empty topic ids!"
        kafka_broker_endpoints = set()
        topic_id_map = {}
        for topic_id in topic_ids:
            response = self.create_topic(topic_id)
            topic_id_map[topic_id] = response["topic_uid"]
            for kafka_broker_endpoint in response["kafka_broker_endpoints"]:
                kafka_broker_endpoints.add(kafka_broker_endpoint)
        kafka_broker_endpoints = list(kafka_broker_endpoints)
        producer = KafkaMessageProducer(kafka_broker_endpoints, topic_id_map)
        return producer

    def create_consumer(
        self,
        topic_id: str,
        auto_offset_reset: str = "earliest",
        consumer_timeout_ms: int = 30000,
        consumer_message_batch_size: int = 16,
        ) -> KafkaMessageConsumer:
        """Subscribes to the topic_id on the Archetype kafka service and returns a consumer for them."""
        assert topic_id, "Empty topic id!"
        response = self.subscribe_topic(topic_id)
        topic_uid = response["topic_uid"]
        kafka_broker_endpoints = response["kafka_broker_endpoints"]
        consumer = KafkaMessageConsumer(
            kafka_broker_endpoints,
            topic_uid,
            auto_offset_reset=auto_offset_reset,
            consumer_timeout_ms=consumer_timeout_ms,
            consumer_message_batch_size=consumer_message_batch_size,
        )
        return consumer