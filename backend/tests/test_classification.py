import pytest

from app.models.enums import RequestIntent
from app.services.llm_provider import MockLLMProvider


@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("I need a new laptop for my onboarding", RequestIntent.IT_EQUIPMENT),
        ("Can I get access to the production database", RequestIntent.DATA_ACCESS),
        ("I want to book a flight and hotel for a client visit", RequestIntent.TRAVEL_BOOKING),
        (
            "I need to submit an expense reimbursement for my client dinner receipt",
            RequestIntent.EXPENSE_REIMBURSEMENT,
        ),
        ("How much PTO do I have left, I want to take a vacation", RequestIntent.TIME_OFF),
        ("I want to work from home next week", RequestIntent.REMOTE_WORK),
        (
            "I think I clicked a phishing link, is this a security incident",
            RequestIntent.SECURITY_INCIDENT,
        ),
        ("What's the weather like today", RequestIntent.OTHER),
    ],
)
def test_mock_llm_provider_classifies_intent(query, expected_intent):
    provider = MockLLMProvider()
    result = provider.classify(query)
    assert result.intent == expected_intent
    assert 0.0 <= result.confidence <= 1.0
    assert result.reasoning


def test_classify_request_endpoint(client, sample_employee):
    create_response = client.post(
        "/api/requests",
        json={"employee_id": sample_employee.id, "raw_query": "I need a new laptop, mine broke"},
    )
    assert create_response.status_code == 201
    request_id = create_response.json()["id"]

    classify_response = client.post(f"/api/requests/{request_id}/classify")
    assert classify_response.status_code == 200
    body = classify_response.json()
    assert body["status"] == "CLASSIFIED"
    assert body["intent"] == "IT_EQUIPMENT"
    assert body["classification_confidence"] > 0
    assert body["classification_reasoning"]


def test_classify_unknown_request_returns_404(client):
    response = client.post("/api/requests/00000000-0000-0000-0000-000000000000/classify")
    assert response.status_code == 404
