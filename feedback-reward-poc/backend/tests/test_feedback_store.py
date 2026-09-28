import os
from uuid import uuid4

import pytest

from feedback_store import FeedbackStore


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("MONGODB_DATABASE", "feedback_reward_test_" + uuid4().hex)
    monkeypatch.setenv("MONGODB_URI", "mongodb://127.0.0.1:27017/")
    store = FeedbackStore()
    store.ping()
    yield store
    store.client.drop_database(os.environ["MONGODB_DATABASE"])
    store.close()


def test_save_reconnect_and_idempotency(store):
    identity = str(uuid4())
    request = {"feedback": "Good", "storeId": "bluewater", "loyalCustomer": True}
    result = {"sentiment": "Positive", "genuineFeedback": "No", "rewardEligible": False}
    saved = store.save(identity, request, result)
    with pytest.raises(ValueError):
        store.save(identity, {**request, "loyalCustomer": False}, result)
    reconnected = FeedbackStore()
    try:
        assert reconnected.get(identity) == saved
        assert reconnected.initial(identity, request) == saved
        assert reconnected.list()["items"] == [saved]
        assert saved["store"]["location"] == "Greenhithe, Kent"
    finally:
        reconnected.close()


def test_clarification_retry_and_stale_update(store):
    identity, operation_id = str(uuid4()), str(uuid4())
    initial = {"feedback": "The store is unsafe.", "storeId": "marble-arch", "loyalCustomer": False}
    store.save(identity, initial, {"rewardDecision": "pending"})
    request = {"originalFeedback": initial["feedback"], "feedback": "The ramp was blocked.",
               "ticketId": None, "storeId": "marble-arch", "loyalCustomer": False}
    updated = store.update(identity, operation_id, request, {"rewardDecision": "eligible"})
    assert updated["revision"] == 1
    assert store.update(identity, operation_id, request, {"rewardDecision": "pending"}) == updated
    assert len(store.list()["items"]) == 1
    with pytest.raises(ValueError):
        store.update(identity, str(uuid4()), request, {})
    with pytest.raises(ValueError):
        store.clarification(identity, operation_id, {**request, "feedback": "changed"})


def test_history_pagination(store):
    for index in range(3):
        store.save(str(uuid4()), {"feedback": f"Comment {index}", "storeId": "unspecified", "loyalCustomer": False}, {})
    first = store.list(limit=2)
    second = store.list(first["nextCursor"], limit=2)
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1
    assert second["nextCursor"] is None
    assert not {item["feedbackId"] for item in first["items"]} & {item["feedbackId"] for item in second["items"]}