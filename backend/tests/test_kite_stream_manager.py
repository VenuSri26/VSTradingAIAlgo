from app.kite_stream_manager import KiteStreamManager


def test_subscription_and_connection_lifecycle():
    manager = KiteStreamManager(requested=True, max_batch_size=2, max_queue_size=4)
    status = manager.subscribe([3, 2, 2, 0])
    assert status["subscribed_tokens"] == [2, 3]
    assert manager.mark_connected()["mode"] == "WEBSOCKET"
    disconnected = manager.mark_disconnected("network")
    assert disconnected["mode"] == "REST_FALLBACK"
    assert disconnected["reconnect_attempts"] == 1


def test_batch_classification_and_backpressure():
    manager = KiteStreamManager(requested=True, max_batch_size=2, max_queue_size=3)
    seen = []
    def ingest(tick):
        seen.append(tick["id"])
        return {"status": tick["status"]}
    ticks = [
        {"id": 1, "status": "ACCEPTED"},
        {"id": 2, "status": "IGNORED"},
        {"id": 3, "status": "REJECTED"},
        {"id": 4, "status": "ACCEPTED"},
    ]
    result = manager.ingest_batch(ticks, ingest)
    assert seen == [1, 2, 3]
    assert result["accepted"] == 1
    assert result["ignored"] == 1
    assert result["rejected"] == 1
    assert result["dropped"] == 1
    assert manager.status()["dropped_ticks"] == 1


def test_live_orders_are_always_disabled():
    manager = KiteStreamManager(requested=False)
    assert manager.status()["live_orders_enabled"] is False
