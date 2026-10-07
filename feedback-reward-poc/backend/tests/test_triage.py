from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import customer, staff
from app.api.deps import current_staff
from app.llm import absa
from app.llm.replies import compose
from app.llm.trained_absa import ensure_loaded, trained_responder
from app.llm.triage import enforce_rules, triage
from app.services.customer_emails import format_email
from app.services.rewards import pounds_for
from app.services import feedback as feedback_service


@pytest.mark.parametrize("text", [
    "The glass doors at the store were spotless and welcoming.",
    "No refund needed, the return was handled perfectly yesterday.",
    "I was still waiting in the queue for two minutes.",
    "The colleague checked the allergen information and helped me yesterday.",
])
def test_benign_mentions_are_not_serious_incidents(text):
    assert not absa.analyse(text).has_serious_cue


@pytest.mark.parametrize("text", [
    "I found glass in my sandwich yesterday.",
    "I had an allergic reaction after eating the meal yesterday.",
    "My card was charged twice yesterday at the checkout.",
    "I am still waiting for my refund after three weeks.",
    "The chicken was out of date and smelled so bad I was sick yesterday.",
    "The packaging did not list the allergen and I had a reaction yesterday.",
    "The milk was expired and I was vomiting after drinking it yesterday.",
])
def test_actual_incidents_remain_serious(text):
    assert absa.analyse(text).has_serious_cue
    result = trained_responder("triage", {"feedback": text, "stars": 1}, {})
    assert result["category"] == "serious_complaint"
    assert result["needs_ticket"]


def test_low_rating_does_not_reverse_clear_praise():
    text = "The staff were helpful yesterday at the checkout."
    result = trained_responder("triage", {
        "feedback": text, "stars": 1,
    }, {})
    assert result["category"] in {"minor_compliment", "major_compliment"}
    assert result["overall_sentiment"] == "positive"
    assert result["needs_review"]
    assert not result["needs_ticket"]
    assert result["reward_tier"] != "low"
    bundle = ensure_loaded()
    features = bundle["vectorizer"].transform([f"STARS_1 {text}"])
    probabilities = bundle["category_clf"].predict_proba(features)[0]
    classes = list(bundle["category_clf"].classes_)
    expected_confidence = round(float(probabilities[classes.index(result["category"])]), 3)
    assert result["category_confidence"] == expected_confidence
    assert result["trace"]["category_confidence"] == expected_confidence


def test_negated_complaint_does_not_become_a_serious_incident():
    result = trained_responder("triage", {
        "feedback": "The staff were not rude and helped me find a shirt yesterday.", "stars": 5,
    }, {})
    assert result["category"] in {"minor_compliment", "major_compliment"}
    assert not result["needs_ticket"]
    staff = [aspect for aspect in result["aspects"] if aspect["aspect"] == "staff_service"]
    assert staff and all(aspect["sentiment"] == "positive" for aspect in staff)


def test_refund_praise_does_not_invent_a_checkout_or_payment_problem():
    result = trained_responder("triage", {
        "feedback": "No refund needed, the return was handled perfectly yesterday.", "stars": 5,
    }, {})
    assert result["category"] in {"minor_compliment", "major_compliment"}
    assert not result["needs_ticket"]
    assert "checkout_payment" not in {aspect["aspect"] for aspect in result["aspects"]}


def test_mixed_feedback_keeps_both_polarities_and_requires_review():
    result = trained_responder("triage", {
        "feedback": "The bread was stale but the staff were lovely yesterday.", "stars": 3,
    }, {})
    assert result["category"] == "minor_complaint"
    assert result["overall_sentiment"] == "mixed"
    assert result["needs_review"]


@pytest.mark.parametrize("category,detailed,genuine,loyal,tier,ticket", [
    ("gibberish", True, False, False, "none", False),
    ("gibberish", True, False, True, "none", False),
    ("minor_compliment", False, True, False, "none", False),
    ("minor_complaint", False, True, False, "none", False),
    ("minor_complaint", True, True, False, "none", True),
    ("major_compliment", False, True, False, "mid", False),
    ("serious_complaint", False, True, False, "high", True),
    ("serious_complaint", True, False, False, "none", True),
    ("minor_compliment", False, True, True, "high", False),
    ("minor_complaint", False, True, True, "high", False),
    ("major_compliment", True, True, True, "high", False),
])
def test_shared_policy_controls_gbp_tier_and_ticket(category, detailed, genuine, loyal, tier, ticket):
    result = {
        "category": category, "has_sufficient_detail": detailed, "genuine": genuine,
        "sparks_member": loyal,
        "reward_tier": "high", "needs_ticket": True,
        "trace": {"reward": {"tier": "high"}, "ticket": {"opened": True}},
    }
    enforce_rules(result)
    assert result["reward_tier"] == tier
    if tier == "none":
        assert pounds_for(tier) == Decimal("0.00")
    else:
        assert pounds_for(tier) > Decimal("0.00")
    assert result["needs_ticket"] is ticket
    assert result["trace"]["reward"]["tier"] == tier
    assert result["trace"]["ticket"]["opened"] is ticket


def test_reward_tiers_use_configured_gbp_amounts():
    assert pounds_for("low") == Decimal("2.00")
    assert pounds_for("mid") == Decimal("3.50")
    assert pounds_for("high") == Decimal("5.00")


def test_genuine_major_and_serious_feedback_do_not_need_detail_for_incentives():
    for category, tier in (("major_compliment", "mid"), ("serious_complaint", "high")):
        result = {"category": category, "genuine": True, "has_sufficient_detail": False}
        enforce_rules(result)
        assert result["reward_tier"] == tier


def test_missing_genuine_signal_never_recommends_incentive():
    result = {"category": "serious_complaint", "has_sufficient_detail": True}
    enforce_rules(result)
    assert result["reward_tier"] == "none"


def test_triage_passes_sparks_membership_to_the_high_tier_rule():
    payload = {}

    def ask(request):
        payload.update(request.payload)
        return {
            "category": "minor_compliment", "genuine": True,
            "has_sufficient_detail": False, "reward_tier": "none",
            "needs_ticket": False, "priority": "low",
            "customer_reply": "Thank you.", "staff_summary": "Kind words",
        }

    result = triage(SimpleNamespace(ask=ask), "Lovely service today.", 5, "bluewater", sparks_member=True)

    assert payload["sparks_member"] is True
    assert result["reward_tier"] == "high"


@pytest.mark.parametrize("sparks_member", [False, True])
def test_customer_reply_does_not_claim_fulfilment_or_contact(sparks_member):
    reply = compose(
        category="serious_complaint", text="My card was charged twice yesterday.",
        aspects=[], detailed=True, missing=[], needs_ticket=True, reward_tier="high",
        sparks_member=sparks_member, reward_amount_gbp=5.00,
    )
    assert "£5.00 incentive" in reply
    assert "suggested for a colleague to review" in reply
    assert "Sparks wallet" not in reply
    assert "will contact you directly" not in reply
    assert "We've passed this" not in reply


@pytest.mark.parametrize("category,detailed,genuine,expected_tier,expected_ticket", [
    ("minor_compliment", True, True, "none", False),
    ("minor_complaint", False, True, "none", False),
    ("major_compliment", True, True, "mid", False),
    ("serious_complaint", True, True, "high", True),
    ("serious_complaint", True, False, "none", True),
])
def test_submission_and_analyser_use_the_same_policy(
    monkeypatch, category, detailed, genuine, expected_tier, expected_ticket,
):
    events = []
    email_records = []
    prediction = {
        "category": category, "has_sufficient_detail": detailed, "genuine": genuine,
        "reward_tier": "high", "needs_ticket": True, "priority": "high",
        "staff_summary": "Feedback for review", "aspects": [],
    }

    def ask(request):
        events.append("analysis")
        return deepcopy(prediction)

    ai = SimpleNamespace(
        model="test", prompt_version="test",
        responder=lambda *args: deepcopy(prediction),
        ask=ask,
    )
    app = FastAPI()
    app.state.ai = ai
    app.include_router(customer.router)
    app.include_router(staff.router)
    app.dependency_overrides[current_staff] = lambda: {"username": "test"}
    saved_analysis = Mock()
    monkeypatch.setattr(feedback_service, "_save_feedback_doc", Mock())
    monkeypatch.setattr(feedback_service, "_save_analysis_doc", saved_analysis)

    def record_email(_payload, kind, subject, body):
        events.append(kind)
        email_records.append({"kind": kind, "subject": subject, "body": body})
        return {"body": format_email(subject, body)}

    monkeypatch.setattr(feedback_service, "_record_customer_email", record_email)
    open_ticket = Mock(return_value={"id": 17})
    monkeypatch.setattr(feedback_service.tickets, "open_ticket", open_ticket)
    monkeypatch.setattr(feedback_service.mongo, "next_id", lambda _name: 1)
    monkeypatch.setattr(feedback_service.mongo, "rewards_collection", lambda: Mock())
    monkeypatch.setattr(feedback_service.mongo, "analysis_collection", lambda: Mock())

    with TestClient(app) as client:
        stores = client.get("/api/stores")
        assert stores.status_code == 200
        assert {store["id"] for store in stores.json()} == {
            "marble-arch", "stratford-city", "bluewater", "unspecified",
        }
        submission = client.post("/api/feedback", json={
            "name": "Demo Customer", "email": "demo@example.test", "store_id": "bluewater",
            "stars": 3, "feedback": "Feedback about my visit to the store yesterday.",
        })
        analysis = client.post("/api/staff/analyse", json={
            "stars": 3, "feedback": "Feedback about my visit to the store yesterday.",
        })

    assert submission.status_code == analysis.status_code == 200
    submitted = submission.json()
    analysed = analysis.json()
    expected_amount = float(pounds_for(expected_tier))
    assert submitted["reward"]["tier"] == expected_tier
    assert submitted["reward"]["tier"] == analysed["reward_tier"]
    assert submitted["reward"]["amount_gbp"] == expected_amount
    assert submitted["customer_reply"] == feedback_service.GENERIC_ACK_BODY
    assert (submitted["ticket_id"] is not None) == analysed["needs_ticket"] == expected_ticket
    assert saved_analysis.call_args.args[1]["reward_tier"] == analysed["reward_tier"]
    assert submitted["reward"]["status"] == "awaiting_eligibility_review"
    assert events[0] == "acknowledgement"
    assert events[1] == "analysis"
    assert submitted["reward_followup"] is None
    assert [record["kind"] for record in email_records] == ["acknowledgement"]
    assert "Subject: We've received your feedback" in submitted["customer_reply"]
    if category == "serious_complaint":
        assert open_ticket.call_args.kwargs["assignee"] == "Customer Care"


def test_customer_email_record_key_is_stable_for_retry(monkeypatch):
    collection = Mock()
    collection.find_one.return_value = {"body": "the original message"}
    monkeypatch.setattr(feedback_service.mongo, "customer_emails_collection", lambda: collection)
    payload = SimpleNamespace(email="customer@example.test", submission_id="submission-123")

    first = feedback_service._record_customer_email(payload, "acknowledgement", "Subject", "First")
    second = feedback_service._record_customer_email(payload, "acknowledgement", "Subject", "Retry")

    assert first["body"] == second["body"] == "the original message"
    first_filter = collection.update_one.call_args_list[0].args[0]
    second_filter = collection.update_one.call_args_list[1].args[0]
    assert first_filter == second_filter == {"_id": "submission-123:acknowledgement"}
    assert all(call.kwargs["upsert"] for call in collection.update_one.call_args_list)
    assert all("$setOnInsert" in call.args[1] for call in collection.update_one.call_args_list)