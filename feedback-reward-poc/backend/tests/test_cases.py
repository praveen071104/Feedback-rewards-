from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from cases import CaseStore, CustomerSubmission, CaseUpdate, CommunicationRequest, CaseDetail, Insights
from feedback_store import FeedbackStore
from predict import FeedbackPredictor


@pytest.fixture
def store(monkeypatch):
    database = "feedback_reward_test_" + uuid4().hex
    monkeypatch.setenv("MONGODB_DATABASE", database)
    monkeypatch.setenv("MONGODB_URI", "mongodb://127.0.0.1:27017/")
    connection = FeedbackStore()
    connection.ping()
    yield CaseStore(connection.collection.database)
    connection.client.drop_database(database)
    connection.close()


@pytest.fixture(scope="module")
def predictor():
    return FeedbackPredictor()


def submission(**changes):
    return CustomerSubmission(**{
        "submission_id": str(uuid4()), "name": "Sample Customer", "email": "sample@example.com",
        "is_sparks_customer": False, "feedback": "The checkout charged twice for my order yesterday and I lost money.",
        "rating": 2, "store_id": "bluewater", **changes,
    })


def update(**changes):
    return CaseUpdate(**{"operation_id": str(uuid4()), "expected_version": 0, "case_status": "In Progress",
                         "final_decision": "Reward Eligible", "decision_reason": "Useful payment issue.",
                         "confirmed_by": "Demo colleague", "store_id": "bluewater", **changes})


def test_profile_separation_null_sparks_and_real_inference(store, predictor):
    payload = submission(sparks_id="discard-me")
    result = store.submit(payload, predictor)
    detail = CaseDetail.model_validate(store.detail(result["case_id"]))
    assert detail.customer.sparks_id is None
    assert detail.customer.email == payload.email
    assert detail.case_status == "Opened"
    assert detail.created_at.tzinfo is not None
    assert detail.reward_assessment.final_decision is None
    assert detail.sentiment.label == predictor.predict(payload.feedback)["sentiment"]
    assert "DistilBERT" not in detail.sentiment.model_name
    assert "email" not in store.raw(result["case_id"])
    assert "customer" not in store.raw(result["case_id"])
    assert "_id" not in store.detail(result["case_id"])
    assert store.notifications()["unread_count"] == 1
    store.mark_read(result["case_id"])
    store.mark_read(result["case_id"])
    assert store.notifications()["unread_count"] == 0
    assert len(store.detail(result["case_id"])["activity_history"]) == 2


def test_duplicate_retry_and_conflicting_payload(store, predictor):
    payload = submission()
    first = store.submit(payload, predictor)
    assert store.submit(payload, predictor) == first
    assert store.cases.count_documents({}) == store.profiles.count_documents({}) == 1
    with pytest.raises(HTTPException) as error:
        store.submit(payload.model_copy(update={"rating": 4}), predictor)
    assert error.value.status_code == 409


def test_low_confidence_and_sparks(store, predictor, monkeypatch):
    monkeypatch.setenv("REWARD_REVIEW_THRESHOLD", "1")
    identity = store.submit(submission(is_sparks_customer=True, sparks_id="SPARKS123"), predictor)["case_id"]
    detail = store.detail(identity)
    assert detail["customer"]["sparks_id"] == "SPARKS123"
    assert detail["reward_assessment"]["model_recommendation"] == "Awaiting Colleague Review"
    assert detail["reward_assessment"]["final_decision"] is None


def test_decision_communication_versions_and_status_transitions(store, predictor):
    identity = store.submit(submission(), predictor)["case_id"]
    with pytest.raises(HTTPException):
        store.mutate(identity, CommunicationRequest(operation_id=uuid4(), expected_version=0, template="reward_eligible"), "notify")
    payload = update()
    confirmed = store.mutate(identity, payload, "review")
    assert confirmed["reward_assessment"]["confirmed_at"] is not None
    assert store.mutate(identity, payload, "review")["version"] == 1
    with pytest.raises(HTTPException):
        store.mutate(identity, update(expected_version=1, case_status="Opened"), "review")
    with pytest.raises(HTTPException):
        store.mutate(identity, update(), "review")
    communication = CommunicationRequest(operation_id=uuid4(), expected_version=1, template="reward_eligible")
    sent = store.mutate(identity, communication, "notify")
    assert sent["customer_communication"]["is_simulated"]
    assert sent["customer_communication"]["channel"] == "email"
    assert "Sparks account" not in sent["customer_communication"]["message"]
    assert store.mutate(identity, communication, "notify")["version"] == 2
    with pytest.raises(HTTPException):
        store.mutate(identity, update(expected_version=2, case_status="Resolved", final_decision="Awaiting Colleague Review"), "review")
    store.mutate(identity, update(expected_version=2, case_status="Resolved"), "review")
    with pytest.raises(HTTPException):
        store.mutate(identity, update(expected_version=3, case_status="Opened"), "review")


def test_phone_communication_and_insights_filters(store, predictor):
    identity = store.submit(submission(email=None, phone_number="+44 7700 900123", rating=4), predictor)["case_id"]
    store.submit(submission(rating=2, store_id="marble-arch"), predictor)
    sent = store.mutate(identity, CommunicationRequest(operation_id=uuid4(), expected_version=0, template="general"), "notify")
    assert sent["customer_communication"]["channel"] == "phone"
    totals = Insights.model_validate(store.insights())
    assert totals.total == 2
    assert totals.average_rating == 3
    assert totals.decisions == {"Awaiting Colleague Review": 2}
    assert store.insights("bluewater")["total"] == 1
    assert store.list(store_id="bluewater")["total"] == 1
    assert store.list(search="[.*")["total"] == 0
    assert store.list(status="Resolved")["total"] == 0
    assert len(store.list(page_size=1)["items"]) == 1


@pytest.mark.parametrize("changes", [
    {"email": "invalid"}, {"email": "a..b@example.com"}, {"email": "a@example..com"},
    {"email": None, "phone_number": None}, {"phone_number": "abc1234567"}, {"phone_number": "123"},
    {"is_sparks_customer": True}, {"rating": 0}, {"rating": 6}, {"rating": True},
    {"name": "  "}, {"feedback": "1234"}, {"feedback": "\u0000bad"}, {"case_status": "Closed"},
])
def test_invalid_customer_input(changes):
    with pytest.raises(ValidationError):
        submission(**changes)


def test_live_api_workflow_and_websocket(store, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from main import app

    monkeypatch.setenv("FEEDBACK_TICKETS_DB", str(tmp_path / "tickets.sqlite3"))
    with TestClient(app) as client:
        with client.websocket_connect("/colleague/events") as socket:
            assert socket.receive_json()["type"] == "cases_changed"
            payload = submission().model_dump(mode="json")
            response = client.post("/customer-feedback", json=payload)
            assert response.status_code == 200
            identity = response.json()["case_id"]
            assert socket.receive_json()["type"] == "cases_changed"
        assert client.get("/colleague/notifications").json()["unread_count"] == 1
        assert client.get("/colleague/feedback-cases").json()["total"] == 1
        assert client.get(f"/colleague/feedback-cases/{identity}").json()["customer"]["name"] == payload["name"]
        assert client.patch(f"/colleague/notifications/{identity}/read").json()["unread_count"] == 0
        response = client.patch(f"/colleague/feedback-cases/{identity}", json=update().model_dump(mode="json"))
        assert response.status_code == 200
        assert response.json()["reward_assessment"]["final_decision"] == "Reward Eligible"
        communication = CommunicationRequest(operation_id=uuid4(), expected_version=1, template="reward_eligible")
        response = client.post(f"/colleague/feedback-cases/{identity}/notify-customer", json=communication.model_dump(mode="json"))
        assert response.status_code == 200
        assert response.json()["customer_communication"]["is_simulated"] is True
        assert client.get("/colleague/insights").json()["decisions"]["Reward Eligible"] == 1
        assert client.post("/customer-feedback", json={**payload, "email": "bad"}).status_code == 422
        assert client.get("/colleague/feedback-cases?status=Closed").status_code == 422
        assert client.get("/customer_profiles").status_code == 404


def test_partial_submission_retry_and_indexes(store, predictor, monkeypatch):
    payload = submission()
    monkeypatch.setenv("REWARD_REVIEW_THRESHOLD", "invalid")
    with pytest.raises(HTTPException) as error:
        store.submit(payload, predictor)
    assert error.value.status_code == 503
    assert store.profiles.count_documents({}) == 1
    assert store.cases.count_documents({}) == 0
    monkeypatch.setenv("REWARD_REVIEW_THRESHOLD", "0.75")
    store.submit(payload, predictor)
    assert store.profiles.count_documents({}) == store.cases.count_documents({}) == 1
    assert {"customer_id_1", "case_id_1", "store_id_1", "case_status_1", "created_at_1", "notification.is_read_1"} <= set(store.cases.index_information())


def test_access_logging_does_not_include_search_queries():
    import logging
    from main import PrivateQueryFilter

    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                               ("local", "GET", "/colleague/feedback-cases?search=private-content", "1.1", 200), None)
    assert PrivateQueryFilter().filter(record)
    assert "private-content" not in record.getMessage()