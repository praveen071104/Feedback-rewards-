# API Endpoint Reference

This document lists the current local POC API separately from the workflow documentation.

## Base URLs and Authentication

- Frontend requests use `/api/...`; Vite proxies them to FastAPI at `http://127.0.0.1:8000/...`.
- Direct FastAPI calls do not use the `/api` prefix.
- Staff endpoints require the `feedback_admin` session cookie created by `/auth/setup` or `/auth/login`.
- `POST /auth/setup` is available only on localhost before an admin account exists.
- API documentation is available at `http://127.0.0.1:8000/docs` after staff authentication on the same hostname.

## Public and Customer Endpoints

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Returns API model and MongoDB readiness. |
| `GET` | `/stores` | Lists the supported store IDs and labels. |
| `POST` | `/customer-feedback` | Creates a customer profile and feedback case. |
| `GET` | `/auth/status` | Returns current admin-session and first-time setup state. |
| `POST` | `/auth/setup` | Creates the first local admin account and session. |
| `POST` | `/auth/login` | Creates an admin session. |
| `POST` | `/auth/logout` | Revokes the current admin session. |

### `POST /customer-feedback`

This is the normal customer submission endpoint. It persists a profile in `customer_profiles` and a case in `feedback_cases`.

```json
{
  "submission_id": "a UUID",
  "name": "Demo Customer",
  "email": "demo.customer@example.com",
  "phone_number": "+447700900123",
  "is_sparks_customer": false,
  "sparks_id": null,
  "store_id": "bluewater",
  "feedback": "The cakes are fresh but sold out by lunchtime.",
  "rating": 2
}
```

Successful response:

```json
{
  "case_id": "the submitted UUID",
  "status": "submitted"
}
```

## Authenticated Colleague Case Endpoints

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/colleague/feedback-cases` | Lists customer cases. |
| `GET` | `/colleague/feedback-cases/{case_id}` | Returns one case, linked customer profile, and communication templates. |
| `PATCH` | `/colleague/feedback-cases/{case_id}` | Saves a final decision, colleague, reason, note, store, and forward case status. |
| `GET` | `/colleague/notifications` | Returns unread and recent case notifications. |
| `PATCH` | `/colleague/notifications/{case_id}/read` | Marks a notification as read. |
| `POST` | `/colleague/feedback-cases/{case_id}/notify-customer` | Records simulated customer communication. |
| `GET` | `/colleague/insights` | Returns customer-case aggregate metrics. |
| `WS` | `/colleague/events` | Sends authenticated case-change invalidations. |

### `GET /colleague/feedback-cases` Query Parameters

| Parameter | Values or range | Purpose |
| --- | --- | --- |
| `store_id` | configured store ID | Optional store filter. |
| `status` | `Opened`, `In Progress`, `Resolved` | Optional case-status filter. |
| `decision` | `Reward Eligible`, `Not Eligible`, `Awaiting Colleague Review` | Optional final-decision filter. |
| `search` | up to 200 characters | Optional API-only text search by case ID or feedback. It is not shown in the Resolution Hub UI. |
| `page` | integer, minimum `1` | Page number; default `1`. |
| `page_size` | integer `1` to `100` | Page size; default `20`. |

### `PATCH /colleague/feedback-cases/{case_id}`

The request uses snake_case fields and optimistic concurrency. Submit the current `expected_version` and a new `operation_id` UUID. Retrying the same operation is safe; a changed/stale request returns `409`.

```json
{
  "operation_id": "a UUID",
  "expected_version": 0,
  "case_status": "In Progress",
  "final_decision": "Awaiting Colleague Review",
  "decision_reason": "More store investigation is required.",
  "confirmed_by": "Store colleague",
  "colleague_note": "Check bakery replenishment timing.",
  "store_id": "bluewater"
}
```

### `POST /colleague/feedback-cases/{case_id}/notify-customer`

Records a communication simulation. It does not send email or issue rewards.

```json
{
  "operation_id": "a UUID",
  "expected_version": 1,
  "template": "general"
}
```

## Authenticated Legacy Analysis Endpoints

These endpoints support the separate staff analysis/history workflow. They use camelCase request fields and store results in the MongoDB `feedback` collection rather than `feedback_cases`.

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/predict` | Analyses feedback, returns overall sentiment, aspect sentiment, usefulness, reward recommendation, and optional ticket. |
| `GET` | `/feedback` | Lists saved legacy analyses. |
| `POST` | `/clarify` | Reassesses an existing legacy analysis with additional customer detail. |
| `GET` | `/tickets/{ticket_id}` | Gets the legacy ticket snapshot. |
| `GET` | `/tickets/{ticket_id}/workflow` | Gets current SQLite ticket workflow state. |
| `PUT` | `/tickets/{ticket_id}/workflow` | Saves a versioned ticket workflow action. |

### `POST /predict`

```json
{
  "feedback": "The cakes are fresh but sold out by lunchtime.",
  "submissionId": "a UUID",
  "loyalCustomer": false,
  "storeId": "bluewater"
}
```

The response includes overall `sentiment`, `sentimentConfidence`, `genuineFeedback`, `genuineConfidence`, reward fields, and `aspects` entries such as:

```json
{
  "aspect": "Availability",
  "sentiment": "Negative",
  "evidence": "sold out by lunchtime"
}
```

### `GET /feedback` Query Parameters

| Parameter | Values or range | Purpose |
| --- | --- | --- |
| `before` | saved feedback UUID | Optional cursor for older results. |
| `limit` | integer `1` to `200` | Result count; default `100`. |

## Common Responses

| Status | Meaning |
| --- | --- |
| `200` | Request succeeded. |
| `401` | Admin login is required for the endpoint. |
| `403` | Browser origin is disallowed, or local-only setup was attempted remotely. |
| `404` | Requested case, ticket, or cursor was not found. |
| `409` | A request conflicts with a reused ID, stale version, or changed data. Reload and retry with current data. |
| `422` | Request validation failed. |
| `503` | Model, MongoDB, or SQLite storage is unavailable. |

## POC Boundary

All endpoints are local POC endpoints. Customer communication is recorded as a simulation, rewards are recommendations only, and customer feedback does not automatically become model training data.