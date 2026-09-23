import pytest
from fastapi.testclient import TestClient

from main import app
from predict import FeedbackPredictor


APPRECIATION = (
    "I was really struggling to get the pista cookies for the past few days considering everybody loves it. "
    "The stock runs out whenever I visit the store. Thankfully, Mr. Joe helped me with the timings when "
    "the product will be restocked and I was finally able to get it today for my niece who loves it."
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


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
    assert set(result) == {"sentiment", "sentimentConfidence", "genuineFeedback", "genuineConfidence", "rewardEligible", "reason"}
    assert result["rewardEligible"] is eligible
    assert result["rewardEligible"] == (result["genuineFeedback"] == "Yes")
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
    assert predictor.predict("The checkout machines froze during payment.")["rewardEligible"] == (genuine == "Yes")


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
    assert "minimum-detail rule" in result["reason"]


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
    assert "stock-feedback rule" in result["reason"]


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
    assert "alone is too generic" in result["reason"]


def test_models_missing(client):
    app.state.predictor = None
    assert client.get("/health").json()["modelsLoaded"] is False
    assert client.post("/predict", json={"feedback": "Good"}).status_code == 503


def test_missing_model_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="train_sentiment"):
        FeedbackPredictor(tmp_path)


def test_health(client):
    assert client.get("/health").json() == {"status": "ready", "modelsLoaded": True}