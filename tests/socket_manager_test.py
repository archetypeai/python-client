from unittest.mock import patch

from archetypeai._socket_manager import SocketManager


class FakeSocket:
    def __init__(self) -> None:
        self.sent_payloads: list[bytes] = []

    def send_binary(self, message_bytes: bytes) -> None:
        self.sent_payloads.append(message_bytes)


def test_outgoing_message_latency_tracks_send_latency_not_queue_delay() -> None:
    manager = SocketManager("fake-api-key", "https://example.com")
    fake_socket = FakeSocket()
    message = {
        "h": "dm",
        "topic_id": "sensor/pose",
        "data": {"x": 1.0},
        "timestamp": 50.0,
    }

    manager.stats_queue.put({"outgoing_message_queue_latency": 7.5})
    with patch("archetypeai._socket_manager.time.time", side_effect=[100.0, 100.25]):
        assert manager._send_data_message(message, fake_socket)

    assert len(fake_socket.sent_payloads) == 1
    assert manager.get_outgoing_message_queue_latency() == 7.5
    assert manager.get_outgoing_message_latency() == 0.25
    assert manager.get_stats()["outgoing_message_latency"] == 0.25
