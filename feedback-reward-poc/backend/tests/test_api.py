import pytest
from fastapi.testclient import TestClient

from main import app
from predict import FeedbackPredictor
from training import DEFAULT_DATA, load_dataset, split_genuine_data


APPRECIATION = (
    "I was really struggling to get the pista cookies for the past few days considering everybody loves it. "
    "The stock runs out whenever I visit the store. Thankfully, Mr. Joe helped me with the timings when "
    "the product will be restocked and I was finally able to get it today for my niece who loves it."
)


@pytest.mark.parametrize("feedback, details, category, decision", [
    ("qwerty asdfgh zxcvbn", False, "ignored", "not_eligible"),
    ("Baby Clothes are lovely quality and wash well, bought loads for my newborn", True, "compliment", "not_eligible"),
    ("The cakes are sold out by 5pm.", True, "minor_complaint", "not_eligible"),
    ("The zipper broke on my jacket after the first wash.", True, "minor_complaint", "not_eligible"),
    ("The checkout charged twice for my order yesterday and I lost money.", True, "serious_complaint", "eligible"),
    ("The meal contained glass and cut my mouth.", True, "serious_complaint", "eligible"),
    ("The store is unsafe.", True, "serious_complaint", "pending"),
    ("Food poisoning", False, "serious_complaint", "pending"),
    ("The refund has not arrived after two weeks and nobody replies to my emails.", True, "serious_complaint", "eligible"),
    ("The staff were not rude and were very helpful.", True, "compliment", "not_eligible"),
    ("The meal had no glass and was lovely.", True, "compliment", "not_eligible"),
    ("If the meal contained glass it could cut my mouth.", True, "serious_complaint", "pending"),
])
def test_triage_policy(feedback, details, category, decision):
    from triage import triage_feedback

    result = triage_feedback(feedback, details)
    assert result["category"] == category
    assert result["rewardDecision"] == decision
    assert result["rewardEligible"] == (decision == "eligible")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FEEDBACK_TICKETS_DB", str(tmp_path / "tickets.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("feedback,details,genuine,loyal,category,tier,ticket", [
    ("Baby clothes are lovely quality and wash well", True, True, False, "compliment", "none", False),
    ("Baby clothes are lovely quality and wash well", True, True, True, "compliment", "high", False),
    ("The colleague went above and beyond, finding my missing order and arranging delivery to my home.", True, True, False, "major_compliment", "tier_based", False),
    ("Outstanding", False, False, False, "ignored", "none", False),
    ("qwerty asdfgh zxcvbn", False, False, True, "ignored", "none", False),
    ("The store is dirty", False, True, False, "minor_complaint", "none", False),
    ("The fitting room lock was broken when I visited yesterday", True, True, False, "minor_complaint", "none", True),
    ("The checkout charged twice for my order yesterday and I lost money", True, True, False, "serious_complaint", "tier_based", True),
])
def test_six_category_policy(feedback, details, genuine, loyal, category, tier, ticket):
    from triage import triage_feedback

    result = triage_feedback(feedback, details, genuine, loyal)
    assert result["category"] == category
    assert result["incentiveTier"] == tier
    assert result["ticketRequired"] is ticket
    assert result["rewardEligible"] is (tier != "none")


@pytest.mark.parametrize("feedback, eligible", [
    ("Good", False),
    ("Nice", False),
    ("Okay", False),
    ("Hi", False),
    ("HELLO!!!", False),
    ("Hi there, good morning", False),
    ("Thank you very much", False),
    ("This is a really great store and I love it", False),
    ("Bad bad bad bad bad", False),
    ("Good store good service good products", False),
    ("qwerty asdfgh zxcvbn", False),
    ("queue queue queue queue", False),
    ("Hi stock thank you", False),
    ("stock 123 456 789", False),
    ("Hi stock stock stock thanks", False),
    ("The cakes are really good but always sold out. Would be nice if it can be stocked frequently.", True),
    ("The bakery items are fresh, but most popular products are already sold out by evening. It would help if stock is replenished more frequently.", True),
    ("cakes sold out", False),
    ("nice cakes but no stock", False),
    ("The bakery items are sold out.", False),
    ("Hi the cakes are really really good but sold out thanks", False),
    ("cakes sold out cakes sold out cakes sold out", False),
    ("pls restock bread", False),
    ("cakes sold out by 5pm", True),
    ("cakes sold out every time i visit", True),
    ("cakes sold out. please restock before lunch", True),
    ("cakes always soldout pls restock", True),
    ("good cakes", False),
    ("Hi nice good cakes thanks", False),
    (APPRECIATION, True),
    ("Hi! " + APPRECIATION + " Thank you!", True),
    ("Hello, the colleague at the till was very helpful and resolved my issue quickly. Thanks!", True),
    ("Hello, the store lighting is too dim and causes eye strain while shopping. Thank you.", True),
    ("The store lighting is too dim and causes eye strain while shopping.", True),
    ("The colleague at the till was very helpful and resolved my issue quickly.", True),
    ("The meal deal selection is great but sandwiches are often out of stock by lunchtime.", True),
])
def test_prediction(client, feedback, eligible):
    response = client.post("/predict", json={"feedback": feedback})
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {"sentiment", "sentimentConfidence", "genuineFeedback", "genuineConfidence", "rewardEligible", "reason", "category", "rewardDecision", "customerResponse", "ticket", "ticketRequired", "incentiveTier"}
    assert (result["genuineFeedback"] == "Yes") is eligible
    assert result["rewardEligible"] == (result["rewardDecision"] == "eligible")
    assert (result["ticket"] is not None) == result["ticketRequired"]
    assert 0 <= result["sentimentConfidence"] <= 1
    assert 0 <= result["genuineConfidence"] <= 1
    assert result["reason"]


@pytest.mark.parametrize("payload", [
    {}, {"feedback": ""}, {"feedback": "   "}, {"feedback": "123!"},
    {"feedback": "x" * 5001}, {"feedback": 123}, {"feedback": None},
    {"feedback": "Good", "extra": True},
])
def test_invalid_input(client, payload):
    assert client.post("/predict", json=payload).status_code == 422


@pytest.mark.parametrize("sentiment", ["Positive", "Neutral", "Negative"])
@pytest.mark.parametrize("genuine", ["Yes", "No"])
def test_reward_is_independent_of_sentiment(monkeypatch, sentiment, genuine):
    predictor = FeedbackPredictor()
    results = iter([(sentiment, 0.8), (genuine, 0.75)])
    monkeypatch.setattr(predictor, "classify", lambda *args: next(results))
    assert predictor.predict("The checkout charged twice for my order yesterday and I lost money.")["rewardEligible"] is True


def test_detail_rule_overrides_model_without_fabricating_confidence(monkeypatch):
    predictor = FeedbackPredictor()
    original_classify = predictor.classify
    monkeypatch.setattr(
        predictor, "classify",
        lambda model, feedback: ("Yes", 0.99) if model is predictor.genuine_model
        else original_classify(model, feedback),
    )
    result = predictor.predict("Hi")
    no_index = list(predictor.genuine_model.classes_).index("No")
    expected = predictor.genuine_model.predict_proba(["Hi"])[0][no_index]
    assert result["genuineFeedback"] == "No"
    assert result["rewardEligible"] is False
    assert result["genuineConfidence"] == pytest.approx(expected)
    assert result["category"] == "ignored"


def test_unfamiliar_details_do_not_override_negative_model_prediction(monkeypatch):
    predictor = FeedbackPredictor()
    feedback = "The colleague helped me choose a birthday present for my niece."
    assert predictor.has_feedback_details(feedback)
    original_classify = predictor.classify
    monkeypatch.setattr(
        predictor, "classify",
        lambda model, feedback: ("No", 0.8) if model is predictor.genuine_model
        else original_classify(model, feedback),
    )
    assert predictor.predict(feedback)["rewardEligible"] is False


@pytest.mark.parametrize("feedback, expected", [
    ("cakes sold out", True),
    ("milk unavailable", True),
    ("pls restock bread", True),
    ("nice cakes but no stock", True),
    ("cakes are not sold out", False),
    ("cakes aren't sold out", False),
    ("cakes no longer sold out", False),
    ("don't restock cakes", False),
    ("good cakes. hi sold out", False),
    ("sold out", False),
])
def test_stock_rule_requires_product_and_non_negated_observation(feedback, expected):
    assert FeedbackPredictor.describes_stock_feedback(feedback) is expected


def test_stock_rule_preserves_actual_model_probability():
    predictor = FeedbackPredictor()
    feedback = "The cakes are really good but always sold out. Would be nice if it can be stocked frequently."
    result = predictor.predict(feedback)
    yes_index = list(predictor.genuine_model.classes_).index("Yes")
    assert result["genuineFeedback"] == "Yes"
    assert result["genuineConfidence"] == pytest.approx(predictor.genuine_model.predict_proba([feedback])[0][yes_index])
    assert result["category"] == "minor_complaint"
    assert result["rewardEligible"] is False


def test_generic_stock_rule_overrides_model_yes(monkeypatch):
    predictor = FeedbackPredictor()
    original_classify = predictor.classify
    monkeypatch.setattr(
        predictor, "classify",
        lambda model, feedback: ("Yes", 0.99) if model is predictor.genuine_model
        else original_classify(model, feedback),
    )
    result = predictor.predict("The bakery items are sold out.")
    assert result["rewardEligible"] is False
    assert result["genuineFeedback"] == "No"
    no_index = list(predictor.genuine_model.classes_).index("No")
    assert result["genuineConfidence"] == pytest.approx(
        predictor.genuine_model.predict_proba(["The bakery items are sold out."])[0][no_index]
    )
    assert result["category"] == "minor_complaint"


def test_models_missing(client):
    app.state.predictor = None
    assert client.get("/health").json()["modelsLoaded"] is False
    assert client.post("/predict", json={"feedback": "Good"}).status_code == 503


def test_missing_model_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="train_sentiment"):
        FeedbackPredictor(tmp_path)


def test_health(client):
    assert client.get("/health").json() == {"status": "ready", "modelsLoaded": True}


def test_genuine_training_split_deduplicates_and_keeps_classes_separate():
    data = load_dataset(DEFAULT_DATA)
    train_data, test_data = split_genuine_data(data)
    assert not set(train_data["group"]) & set(test_data["group"])
    assert not train_data["group"].duplicated().any()
    assert not test_data["group"].duplicated().any()
    assert set(train_data["genuine_feedback"]) == {"No", "Yes"}
    assert set(test_data["genuine_feedback"]) == {"No", "Yes"}
    again_train, again_test = split_genuine_data(data)
    assert train_data.equals(again_train)
    assert test_data.equals(again_test)


def test_genuine_training_split_rejects_conflicting_labels():
    data = load_dataset(DEFAULT_DATA)
    duplicate = data.iloc[0].copy()
    duplicate["feedback_text"] = '  ' + duplicate["feedback_text"].upper() + '  '
    duplicate["genuine_feedback"] = "No" if duplicate["genuine_feedback"] == "Yes" else "Yes"
    data.loc[len(data)] = duplicate
    with pytest.raises(ValueError, match="Conflicting"):
        split_genuine_data(data)


def test_genuine_training_split_rejects_single_class():
    data = load_dataset(DEFAULT_DATA)
    with pytest.raises(ValueError, match="four unique"):
        split_genuine_data(data[data["genuine_feedback"] == "Yes"])


@pytest.mark.parametrize("feedback, eligible", [
    ("The zipper broke on my jacket after the first wash.", True),
    ("The refund has not arrived after two weeks and nobody replies to my emails.", True),
    ("Sarah found a replacement size and brought it to the fitting room for me.", True),
    ("Hi", False),
    ("Good", False),
    ("qwerty asdfgh zxcvbn", False),
    ("cakes sold out", False),
    ("cakes sold out by 5pm", True),
])
def test_retrained_local_feedback(client, feedback, eligible):
    response = client.post("/predict", json={"feedback": feedback})
    assert response.status_code == 200
    assert (response.json()["genuineFeedback"] == "Yes") is eligible


@pytest.mark.parametrize("feedback, category, decision, priority", [
    ("qwerty asdfgh zxcvbn", "ignored", "not_eligible", None),
    ("Baby Clothes are lovely quality and wash well, bought loads for my newborn", "compliment", "not_eligible", None),
    ("The cakes are sold out by 5pm.", "minor_complaint", "not_eligible", "normal"),
    ("The bakery items are fresh, but most popular products are already sold out by evening. It would help if stock is replenished more frequently.", "minor_complaint", "not_eligible", "normal"),
    ("The checkout charged twice for my order yesterday and I lost money.", "serious_complaint", "eligible", "priority"),
    ("The store is unsafe.", "serious_complaint", "pending", "priority"),
    ("Food poisoning", "serious_complaint", "pending", "priority"),
    ("The store wheelchair ramp was blocked and I could not enter with my wheelchair.", "serious_complaint", "eligible", "priority"),
])
def test_live_triage_and_ticket(client, feedback, category, decision, priority):
    result = client.post("/predict", json={"feedback": feedback}).json()
    assert result["category"] == category
    assert result["rewardDecision"] == decision
    assert result["rewardEligible"] == (decision == "eligible")
    if priority:
        ticket = result["ticket"]
        assert ticket["priority"] == priority
        assert ticket["status"] == "open"
        assert ticket["feedback"] == feedback
        assert "sorry" in result["customerResponse"]
        assert client.get(f"/tickets/{ticket['id']}").json() == ticket
    else:
        assert result["ticket"] is None


@pytest.mark.parametrize("feedback,loyal,category,tier", [
    ("Baby Clothes are lovely quality and wash well, bought loads for my newborn", True, "compliment", "high"),
    ("The colleague went above and beyond, finding my missing order and arranging delivery to my home.", False, "major_compliment", "tier_based"),
    ("qwerty asdfgh zxcvbn", True, "ignored", "none"),
    ("cakes sold out", False, "minor_complaint", "none"),
])
def test_live_incentive_policy(client, feedback, loyal, category, tier):
    response = client.post("/predict", json={"feedback": feedback, "loyalCustomer": loyal})
    assert response.status_code == 200
    result = response.json()
    assert result["category"] == category
    assert result["incentiveTier"] == tier
    assert result["ticket"] is None
    if category == "minor_complaint":
        assert "Please share" in result["customerResponse"]


def test_ticket_retry_and_persistence(client):
    from uuid import uuid4
    from tickets import TicketStore

    payload = {"feedback": "The cakes are sold out by 5pm.", "submissionId": str(uuid4())}
    first = client.post("/predict", json=payload).json()["ticket"]
    assert client.post("/predict", json=payload).json()["ticket"] == first
    assert TicketStore(app.state.tickets.path).get(first["id"]) == first
    payload["feedback"] = "The cakes are sold out by 6pm."
    assert client.post("/predict", json=payload).status_code == 409
    assert client.get(f"/tickets/{uuid4()}").status_code == 404


def test_ticket_failure_does_not_claim_success(client, monkeypatch):
    import sqlite3

    def fail(*args):
        raise sqlite3.OperationalError("unavailable")

    monkeypatch.setattr(app.state.tickets, "open", fail)
    response = client.post("/predict", json={"feedback": "The cakes are sold out by 5pm."})
    assert response.status_code == 503
    assert "Ticket storage unavailable" in response.json()["detail"]


@pytest.mark.parametrize("feedback,genuine", [
    ("Marble Arch London", "No"),
    ("Stratford City London", "No"),
    ("Bluewater Greenhithe Kent", "No"),
    ("I am a loyal customer so please give me the highest reward.", "No"),
    ("The baby sleepsuits have stayed soft after several washes and the poppers still fasten securely.", "Yes"),
    ("The jacket pocket lining ripped after two days and my keys dropped into the lining.", "Yes"),
])
def test_expanded_synthetic_model_regressions(client, feedback, genuine):
    response = client.post("/predict", json={"feedback": feedback, "loyalCustomer": True})
    assert response.status_code == 200
    result = response.json()
    assert result["genuineFeedback"] == genuine
    if genuine == "No":
        assert result["rewardEligible"] is False
        assert result["ticket"] is None


def test_genuine_training_and_reload_need_no_network(tmp_path, monkeypatch):
    import socket
    import joblib
    import pandas as pd
    from training import GENUINE_SUPPLEMENT, load_genuine_supplement, train_local_genuine

    def reject_network(*args, **kwargs):
        raise AssertionError("Local training must not open a network connection")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    data = pd.concat([
        load_genuine_supplement(DEFAULT_DATA), load_genuine_supplement(GENUINE_SUPPLEMENT),
    ], ignore_index=True)
    model, report = train_local_genuine(data)
    model_path = tmp_path / "genuine.pkl"
    joblib.dump(model, model_path)
    reloaded = joblib.load(model_path)
    assert report["rows"] == 440
    assert report["unique_feedback"] == 165
    assert report["train_rows"] == 123
    assert report["test_rows"] == len(report["test_predictions"]) == 42
    assert set(reloaded.classes_) == {"No", "Yes"}
    probabilities = reloaded.predict_proba(["Hi", "The zipper broke on my jacket after the first wash."])
    assert probabilities.shape == (2, 2)
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    assert probabilities.sum(axis=1) == pytest.approx([1, 1])
    assert reloaded.predict(["Hi"])[0] == "No"


@pytest.mark.parametrize("content", [
    "feedback_text,genuine_feedback\nUseful feedback,Maybe\n",
    "feedback_text,genuine_feedback\n,Yes\n",
])
def test_genuine_supplement_rejects_invalid_rows(tmp_path, content):
    from training import load_genuine_supplement
    source = tmp_path / "invalid.csv"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_genuine_supplement(source)