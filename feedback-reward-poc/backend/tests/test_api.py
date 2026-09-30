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


def test_business_evaluation_reports_errors_and_rule_changes():
    import pandas as pd
    from evaluate_genuine import evaluate_cases

    class Predictor:
        genuine_model = None

        def classify(self, model, text):
            return ("Yes", 0.8)

        def predict(self, text):
            return {"genuineFeedback": "No", "genuineConfidence": 0.6}

        def has_feedback_details(self, text):
            return False

    cases = pd.DataFrame([
        {"feedback_text": "Lovely", "genuine_feedback": "No", "characteristic": "generic_praise", "expected_reason": "No detail"},
        {"feedback_text": "The seam split on the first wash", "genuine_feedback": "Yes", "characteristic": "issue_description", "expected_reason": "Specific defect"},
    ])
    report = evaluate_cases(cases, Predictor(), [" LOVELY "])
    assert report["raw_model"]["false_positives"] == 1
    assert report["raw_model"]["false_negatives"] == 0
    assert report["final_pipeline"]["false_negatives"] == 1
    assert report["final_pipeline"]["false_positives"] == 0
    assert report["training_text_overlap_count"] == 1
    assert all(row["rules_changed_label"] for row in report["cases"])
    assert report["by_characteristic"]["issue_description"]["final_pipeline"]["false_negatives"] == 1
    with pytest.raises(ValueError, match="unique"):
        evaluate_cases(pd.concat([cases, cases]), Predictor())
    with pytest.raises(ValueError, match="Yes or No"):
        evaluate_cases(cases.assign(genuine_feedback="Invalid"), Predictor())


def test_business_evaluation_cases_cover_all_requested_characteristics():
    import pandas as pd
    from evaluate_genuine import DEFAULT_CASES, evaluate_cases

    cases = pd.read_csv(DEFAULT_CASES, keep_default_na=False)
    report = evaluate_cases(cases, FeedbackPredictor())
    assert set(report["by_characteristic"]) == {
        "specific_experience", "actions_taken", "employee_interaction", "product_reference", "issue_description",
        "detailed_observation", "generic_praise", "very_short", "repetition", "vague_appreciation", "insufficient_detail",
    }
    assert report["final_pipeline"]["count"] == 22


@pytest.mark.parametrize("feedback,details,genuine,category,decision", [
    ("The cakes are sold out by 5pm. Please restock before the evening rush.", True, True, "minor_complaint", "eligible"),
    ("The zipper broke on my jacket after the first wash.", True, True, "minor_complaint", "eligible"),
    ("Baby clothes are lovely quality and wash well after several washes.", True, True, "compliment", "eligible"),
    ("The colleague at the till was helpful and resolved my issue quickly.", True, True, "compliment", "eligible"),
    ("Please add size labels on the shelves so customers can find the right size.", True, True, "suggestion", "eligible"),
    ("Good store", False, False, "compliment", "not_eligible"),
    ("cakes sold out", True, False, "minor_complaint", "not_eligible"),
    ("Please improve the store", False, False, "ignored", "not_eligible"),
    ("qwerty asdfgh", False, False, "ignored", "not_eligible"),
])
def test_usefulness_reward_policy(feedback, details, genuine, category, decision):
    from triage import triage_feedback

    result = triage_feedback(feedback, details, genuine)
    assert result["category"] == category
    assert result["rewardDecision"] == decision
    assert result["rewardEligible"] is (decision == "eligible")


@pytest.mark.parametrize("feedback,sentiment", [
    ("The cakes are sold out by 5pm. Please restock before the evening rush.", "Negative"),
    ("The cakes are fresh and delicious but sold out by lunchtime.", "Neutral"),
    ("The meal deal selection is great but sandwiches are often out of stock by lunchtime.", "Neutral"),
    ("Baby clothes are lovely quality and wash well after several washes.", "Positive"),
    ("The colleague at the till was helpful and resolved my issue quickly.", "Positive"),
    ("Please add size labels on the shelves so customers can find the right size.", "Neutral"),
    ("The store opens at nine and closes at six.", "Neutral"),
    ("The zipper broke on my jacket after the first wash.", "Negative"),
    ("The store lighting is too dim and causes eye strain while shopping.", "Negative"),
    ("Thanks. The checkout charged twice for my order yesterday.", "Negative"),
    ("The staff were not rude and were helpful.", "Positive"),
    ("The staff were not helpful.", "Negative"),
    ("The service was not good.", "Negative"),
    ("The cakes are not sold out.", "Positive"),
    ("qwerty asdfgh", "Neutral"),
    ("Good", "Positive"),
])
def test_local_retail_sentiment(feedback, sentiment):
    predictor = FeedbackPredictor()
    result, support = predictor.classify_sentiment(feedback)
    assert result in {"Positive", "Neutral", "Negative"}
    assert 0 <= support <= 1


def test_lstm_model_and_artifact_metadata():
    predictor = FeedbackPredictor()
    assert predictor.sentiment_model.__class__.__name__ == "SentimentLSTMClassifier"
    assert predictor.metadata["sentiment"].startswith("local-v1-")
    probabilities = predictor.sentiment_model.predict_proba(["The service was not good."])[0]
    assert len(probabilities) == 3
    assert sum(probabilities) == pytest.approx(1.0)


def test_synthetic_music_feedback_is_classified_positive():
    feedback = (
        "I really love the store experience especially the music being played. The store is playing all the "
        "Billboard 100 hits which is fantastic. I feel M&S can plan for theme based music like MJ tributes, "
        "Halloween special songs, Christmas songs etc. and it will resonate well with everyone."
    )
    assert FeedbackPredictor().classify_sentiment(feedback)[0] == "Positive"


@pytest.mark.parametrize("feedback, details, category, decision", [
    ("qwerty asdfgh zxcvbn", False, "ignored", "not_eligible"),
    ("Baby Clothes are lovely quality and wash well, bought loads for my newborn", True, "compliment", "eligible"),
    ("The cakes are sold out by 5pm.", True, "minor_complaint", "eligible"),
    ("The zipper broke on my jacket after the first wash.", True, "minor_complaint", "eligible"),
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
    from uuid import uuid4

    database = "feedback_reward_test_" + uuid4().hex
    monkeypatch.setenv("MONGODB_DATABASE", database)
    monkeypatch.setenv("MONGODB_URI", "mongodb://127.0.0.1:27017/")
    monkeypatch.setenv("FEEDBACK_TICKETS_DB", str(tmp_path / "tickets.sqlite3"))
    with TestClient(app) as test_client:
        try:
            yield test_client
        finally:
            app.state.feedback.client.drop_database(database)


@pytest.mark.parametrize("feedback,details,genuine,loyal,category,tier,ticket", [
    ("Baby clothes are lovely quality and wash well", True, True, False, "compliment", "tier_based", False),
    ("Baby clothes are lovely quality and wash well", True, True, True, "compliment", "high", False),
    ("The colleague went above and beyond, finding my missing order and arranging delivery to my home.", True, True, False, "major_compliment", "tier_based", False),
    ("Outstanding", False, False, False, "ignored", "none", False),
    ("qwerty asdfgh zxcvbn", False, False, True, "ignored", "none", False),
    ("The store is dirty", False, True, False, "minor_complaint", "none", False),
    ("The fitting room lock was broken when I visited yesterday", True, True, False, "minor_complaint", "tier_based", True),
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
    assert set(result) == {"sentiment", "sentimentConfidence", "genuineFeedback", "genuineConfidence", "rewardEligible", "reason", "category", "rewardDecision", "customerResponse", "ticket", "ticketRequired", "incentiveTier", "clarificationQuestions", "feedbackId", "feedback", "storeId", "store", "loyalCustomer", "createdAt", "updatedAt", "revision"}
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
    monkeypatch.setattr(predictor, "classify_sentiment", lambda *args: (sentiment, 0.8))
    monkeypatch.setattr(predictor, "classify", lambda *args: (genuine, 0.75))
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
    assert result["rewardEligible"] is True


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


def test_loyal_genuine_feedback_receives_high_tier_independent_of_base_reward():
    from triage import triage_feedback

    text = "The shelf labels show product sizes clearly."
    standard = triage_feedback(text, True, True, False)
    loyal = triage_feedback(text, True, True, True)
    assert standard["rewardEligible"] is False
    assert loyal["rewardEligible"] is True
    assert loyal["incentiveTier"] == "high"
    assert loyal["clarificationQuestions"] == standard["clarificationQuestions"]
    assert triage_feedback("qwerty asdfgh", False, False, True)["rewardEligible"] is False
    assert triage_feedback(text, True, False, True)["rewardEligible"] is False


def test_ticket_workflow_assignment_resolution_retry_and_persistence(client):
    from uuid import uuid4
    from tickets import TicketStore

    saved = client.post("/predict", json={"feedback": "The store is unsafe."}).json()
    ticket_id = saved["ticket"]["id"]
    url = f"/tickets/{ticket_id}/workflow"
    assert client.get(url).json()["version"] == 0
    payload = {"operationId": str(uuid4()), "expectedVersion": 0, "assignee": "Store colleague",
               "status": "in_progress", "actionTaken": "Inspected the ramp", "customerEmail": "customer@example.com",
               "contactConsent": True, "customerUpdate": "We are checking the ramp.", "contactStatus": "not_contacted"}
    first = client.put(url, json=payload)
    assert first.status_code == 200
    assert client.put(url, json=payload).json() == first.json()
    assert client.put(url, json={**payload, "actionTaken": "Changed"}).status_code == 409
    assert client.put(url, json={**payload, "operationId": str(uuid4())}).status_code == 409
    resolved = client.put(url, json={**payload, "operationId": str(uuid4()), "expectedVersion": 1,
        "status": "resolved", "actionTaken": "Cleared the ramp and checked access.",
        "customerUpdate": "The ramp is now clear.", "contactStatus": "contact_recorded"}).json()
    assert resolved["version"] == 2
    assert len(resolved["history"]) == 2
    assert TicketStore(app.state.tickets.path).workflow(ticket_id) == resolved
    assert client.put(url, json=payload).json() == first.json()
    assert client.get(url).json() == resolved
    assert client.put(url, json={**payload, "operationId": str(uuid4()), "expectedVersion": 2}).status_code == 409
    assert client.get(f"/tickets/{uuid4()}/workflow").status_code == 404


@pytest.mark.parametrize("changes", [
    {"status": "in_progress"}, {"status": "resolved", "assignee": "Colleague"},
    {"customerEmail": "customer@example.com"}, {"customerEmail": "invalid", "contactConsent": True},
    {"contactStatus": "contact_recorded"}, {"assignee": " " , "status": "in_progress"},
])
def test_ticket_workflow_validation(client, changes):
    from uuid import uuid4

    payload = {"operationId": str(uuid4()), "expectedVersion": 0, **changes}
    assert client.put(f"/tickets/{uuid4()}/workflow", json=payload).status_code == 422


def test_models_missing(client):
    app.state.predictor = None
    assert client.get("/health").json()["modelsLoaded"] is False
    assert client.post("/predict", json={"feedback": "Good"}).status_code == 503


def test_missing_model_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="train_sentiment"):
        FeedbackPredictor(tmp_path)


def test_health(client):
    assert client.get("/health").json() == {"status": "ready", "modelsLoaded": True, "storageReady": True}


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
    ("Baby Clothes are lovely quality and wash well, bought loads for my newborn", "compliment", "eligible", None),
    ("The cakes are sold out by 5pm.", "minor_complaint", "eligible", "normal"),
    ("The bakery items are fresh, but most popular products are already sold out by evening. It would help if stock is replenished more frequently.", "minor_complaint", "eligible", "normal"),
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


@pytest.mark.parametrize("feedback,decision", [
    ("The checkout charged twice for my order yesterday and I lost money.", "eligible"),
    ("The colleague went above and beyond, finding my missing order and arranging delivery to my home.", "eligible"),
    ("Baby Clothes are lovely quality and wash well, bought loads for my newborn", "eligible"),
    ("The zipper broke on my jacket after the first wash.", "eligible"),
    ("The store is unsafe.", "pending"),
    ("qwerty asdfgh zxcvbn", "not_eligible"),
])
def test_loyalty_high_tier_preserves_category_and_ticket(client, feedback, decision):
    standard = client.post("/predict", json={"feedback": feedback, "loyalCustomer": False}).json()
    loyal = client.post("/predict", json={"feedback": feedback, "loyalCustomer": True}).json()
    assert standard["rewardDecision"] == loyal["rewardDecision"] == decision
    for field in ["category", "genuineFeedback", "ticketRequired", "rewardEligible"]:
        assert standard[field] == loyal[field]
    assert standard["incentiveTier"] == ("tier_based" if decision == "eligible" else "none")
    assert loyal["incentiveTier"] == ("high" if decision == "eligible" else "none")
    if decision == "eligible":
        assert "high-tier" in loyal["reason"]


def test_targeted_automatic_clarification():
    from triage import triage_feedback

    vague = triage_feedback("The store is unsafe.", False)
    assert "How did the issue affect you?" in vague["clarificationQuestions"]
    assert "Which product or service was involved?" not in vague["clarificationQuestions"]
    detailed = triage_feedback("The store ramp was blocked and I could not enter with my wheelchair.", True)
    assert detailed["rewardDecision"] == "eligible"
    assert detailed["clarificationQuestions"] == []
    assert triage_feedback("qwerty asdfgh", False, False)["clarificationQuestions"] == []


def test_clarification_automatically_reassesses_same_ticket(client):
    from uuid import uuid4

    original = "The store is unsafe."
    first = client.post("/predict", json={"feedback": original, "loyalCustomer": True}).json()
    assert first["rewardDecision"] == "pending"
    payload = {
        "feedbackId": first["feedbackId"],
        "originalFeedback": original,
        "feedback": "The wheelchair ramp was blocked and I could not enter the store yesterday.",
        "ticketId": first["ticket"]["id"], "submissionId": str(uuid4()), "loyalCustomer": True,
    }
    response = client.post("/clarify", json=payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["rewardDecision"] == "eligible"
    assert updated["incentiveTier"] == "high"
    assert updated["clarificationQuestions"] == []
    assert updated["ticket"]["id"] == first["ticket"]["id"]
    assert updated["ticket"]["createdAt"] == first["ticket"]["createdAt"]
    assert updated["ticket"]["feedback"] == original + "\n\n" + payload["feedback"]
    assert client.post("/clarify", json=payload).json() == updated
    assert client.get(f"/tickets/{first['ticket']['id']}").json() == updated["ticket"]
    assert client.post("/clarify", json={**payload, "feedback": "Different reply"}).status_code == 409
    assert client.post("/clarify", json={**payload, "submissionId": str(uuid4())}).status_code == 409
    assert client.post("/clarify", json={**payload, "feedbackId": str(uuid4()), "submissionId": str(uuid4())}).status_code == 404


def test_clarification_keeps_asking_and_preserves_conversation(client):
    from uuid import uuid4

    original = "The store is unsafe."
    first = client.post("/predict", json={"feedback": original}).json()
    payload = {"feedbackId": first["feedbackId"], "originalFeedback": original, "feedback": "qwerty asdfgh", "ticketId": first["ticket"]["id"], "submissionId": str(uuid4())}
    second = client.post("/clarify", json=payload).json()
    assert second["rewardDecision"] == "pending"
    assert second["clarificationQuestions"]
    third = client.post("/clarify", json={**payload, "originalFeedback": second["ticket"]["feedback"],
        "feedback": "The checkout charged twice for my order yesterday and I lost money.", "submissionId": str(uuid4())}).json()
    assert third["rewardDecision"] == "eligible"
    assert third["ticket"]["id"] == first["ticket"]["id"]
    assert client.post("/clarify", json=payload).json() == second
    assert client.get(f"/tickets/{first['ticket']['id']}").json() == third["ticket"]


def test_minor_clarification_opens_one_ticket_after_details(client):
    from uuid import uuid4

    original = "cakes sold out"
    first = client.post("/predict", json={"feedback": original}).json()
    assert first["ticket"] is None
    payload = {"feedbackId": first["feedbackId"], "originalFeedback": original, "feedback": "The cakes are sold out by 5pm every Friday when I visit after work.", "submissionId": str(uuid4())}
    response = client.post("/clarify", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["ticket"]["priority"] == "normal"
    assert result["rewardDecision"] == "eligible"
    assert result["clarificationQuestions"] == []
    assert client.post("/clarify", json=payload).json()["ticket"] == result["ticket"]


@pytest.mark.parametrize("changes", [
    {"feedback": " "}, {"feedback": "123"}, {"originalFeedback": " "},
    {"feedback": "a" * 4990}, {"ticketId": "invalid"}, {"loyalCustomer": "yes"},
])
def test_clarification_validation(client, changes):
    payload = {"originalFeedback": "The store is unsafe.", "feedback": "More details", **changes}
    assert client.post("/clarify", json=payload).status_code == 422


def test_clarification_requires_open_question_and_ticket_reference(client):
    saved = client.post("/predict", json={"feedback": "Good"}).json()
    assert client.post("/clarify", json={"feedbackId": saved["feedbackId"], "originalFeedback": "Good", "feedback": "More information"}).status_code == 409
    assert client.post("/clarify", json={"originalFeedback": "The store is unsafe.", "feedback": "More information"}).status_code == 422


def test_clarification_storage_failure_preserves_original(client, monkeypatch):
    import sqlite3

    original = "The store is unsafe."
    first = client.post("/predict", json={"feedback": original}).json()

    def fail(*args):
        raise sqlite3.OperationalError("unavailable")

    monkeypatch.setattr(app.state.tickets, "reassess", fail)
    response = client.post("/clarify", json={"feedbackId": first["feedbackId"], "originalFeedback": original, "ticketId": first["ticket"]["id"],
        "feedback": "The checkout charged twice for my order yesterday and I lost money."})
    assert response.status_code == 503
    assert "Ticket storage unavailable" in response.json()["detail"]
    assert client.get(f"/tickets/{first['ticket']['id']}").json() == first["ticket"]


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


def test_mongodb_history_metadata_and_reconnect(client):
    from feedback_store import FeedbackStore
    from uuid import uuid4

    payload = {"feedback": "qwerty asdfgh", "submissionId": str(uuid4()), "storeId": "bluewater", "loyalCustomer": True}
    saved = client.post("/predict", json=payload).json()
    assert saved["category"] == "ignored"
    assert saved["genuineFeedback"] == "No"
    assert saved["rewardEligible"] is False
    assert saved["loyalCustomer"] is True
    assert saved["store"] == {"name": "M&S Bluewater", "location": "Greenhithe, Kent"}
    assert saved["createdAt"] == saved["updatedAt"]
    assert saved["revision"] == 0
    assert client.post("/predict", json=payload).json() == saved
    assert client.post("/predict", json={**payload, "storeId": "marble-arch"}).status_code == 409
    assert client.get("/feedback").json() == {"items": [saved], "nextCursor": None}
    reconnected = FeedbackStore()
    try:
        assert reconnected.get(saved["feedbackId"]) == saved
    finally:
        reconnected.close()
    assert client.post("/predict", json={"feedback": "Good", "storeId": "invalid"}).status_code == 422
    assert client.get("/feedback?limit=0").status_code == 422
    assert client.get("/feedback?before=invalid").status_code == 422
    assert client.get(f"/feedback?before={uuid4()}").status_code == 404
    assert len(client.get("/stores").json()) == 4


def test_mongodb_clarification_preserves_metadata_and_one_record(client):
    from uuid import uuid4

    first = client.post("/predict", json={"feedback": "The store is unsafe.", "storeId": "stratford-city", "loyalCustomer": True}).json()
    payload = {"feedbackId": first["feedbackId"], "originalFeedback": first["feedback"],
               "feedback": "The wheelchair ramp was blocked and I could not enter yesterday.",
               "ticketId": first["ticket"]["id"], "storeId": first["storeId"], "loyalCustomer": True, "submissionId": str(uuid4())}
    assert client.post("/clarify", json={**payload, "loyalCustomer": False}).status_code == 409
    assert client.post("/clarify", json={**payload, "storeId": "bluewater"}).status_code == 409
    updated = client.post("/clarify", json=payload).json()
    assert updated["revision"] == 1
    assert updated["feedbackId"] == first["feedbackId"]
    assert updated["createdAt"] == first["createdAt"]
    assert updated["rewardEligible"] is True
    assert client.get("/feedback").json()["items"] == [updated]
    assert client.post("/clarify", json=payload).json() == updated


def test_mongodb_write_failure_can_be_retried_after_ticket_creation(client, monkeypatch):
    from pymongo.errors import AutoReconnect
    from uuid import uuid4

    payload = {"feedback": "The checkout charged twice for my order yesterday and I lost money.", "submissionId": str(uuid4())}
    save = app.state.feedback.save

    def fail(*args):
        raise AutoReconnect("unavailable")

    monkeypatch.setattr(app.state.feedback, "save", fail)
    response = client.post("/predict", json=payload)
    assert response.status_code == 503
    assert "saving was not confirmed" in response.json()["detail"]
    monkeypatch.setattr(app.state.feedback, "save", save)
    saved = client.post("/predict", json=payload).json()
    assert client.post("/predict", json=payload).json() == saved
    assert len(client.get("/feedback").json()["items"]) == 1


def test_mongodb_read_outage_does_not_create_ticket(client, monkeypatch):
    from pymongo.errors import AutoReconnect

    def fail(*args):
        raise AutoReconnect("unavailable")

    def unexpected(*args):
        pytest.fail("Ticket must not be opened when feedback storage cannot be read")

    monkeypatch.setattr(app.state.feedback, "initial", fail)
    monkeypatch.setattr(app.state.feedback, "list", fail)
    monkeypatch.setattr(app.state.feedback, "ping", fail)
    monkeypatch.setattr(app.state.tickets, "open", unexpected)
    assert client.post("/predict", json={"feedback": "The cakes are sold out by 5pm."}).status_code == 503
    assert client.get("/feedback").status_code == 503
    assert client.get("/health").json()["storageReady"] is False


def test_mongodb_clarification_write_retry_repairs_partial_save(client, monkeypatch):
    from pymongo.errors import AutoReconnect
    from uuid import uuid4

    first = client.post("/predict", json={"feedback": "The store is unsafe."}).json()
    payload = {"feedbackId": first["feedbackId"], "originalFeedback": first["feedback"],
               "feedback": "The wheelchair ramp was blocked and I could not enter yesterday.",
               "ticketId": first["ticket"]["id"], "submissionId": str(uuid4())}
    update = app.state.feedback.update

    def fail(*args):
        raise AutoReconnect("unavailable")

    monkeypatch.setattr(app.state.feedback, "update", fail)
    assert client.post("/clarify", json=payload).status_code == 503
    assert client.get("/feedback").json()["items"] == [first]
    ticket = client.get(f"/tickets/{first['ticket']['id']}").json()
    assert ticket["rewardDecision"] == "eligible"
    monkeypatch.setattr(app.state.feedback, "update", update)
    updated = client.post("/clarify", json=payload).json()
    assert updated["revision"] == 1
    assert updated["ticket"] == ticket
    assert updated["feedbackId"] == first["feedbackId"]
    assert client.get("/feedback").json()["items"] == [updated]
    assert client.post("/clarify", json=payload).json() == updated


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