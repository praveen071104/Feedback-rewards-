# Feedback Classification and Incentives

This describes the current `backend/app` implementation, not the older LSTM/SQLite workflow described in some existing documents. Customer submissions and the staff analyser use the same enforced policy.

## GBP Incentive Policy

| Category | Required action | Recommended incentive | Ticket |
| --- | --- | ---: | --- |
| Minor compliment | Thank the customer with context and record what went well | None, unless loyal | No |
| Gibberish, test text or spam | Ignore; do not create a case or incentive | None | No |
| Minor complaint | Apologise; request missing details and record that action, or open a ticket when actionable | None, unless loyal | Only when sufficiently detailed |
| Major compliment | Thank the customer | Mid (£3.50) if genuine; high for loyal customers | No |
| Serious complaint | Apologise, open a high-priority ticket assigned to Customer Care, and retain customer contact details for follow-up | High (£5.00) if genuine | Always |
| Genuine feedback from a loyal Sparks member | Apply the loyalty incentive, regardless of category | High (£5.00) | Category rules still apply |
| Gibberish or non-genuine feedback | Never eligible | None | Complaint escalation still follows category rules |

The configured GBP amounts are low = £2.00, mid = £3.50 and high = £5.00. `FEEDBACK_REWARD_LOW_GBP`, `FEEDBACK_REWARD_MID_GBP` and `FEEDBACK_REWARD_HIGH_GBP` can change them. A colleague's eligible decision creates an `issued` reward record. The app does not connect to a payment or Sparks account system, so this records the decision but does not transfer money or credit an external balance.

## Manual Eligibility Gate

The analyser's tier is a suggestion only. Every submission is available from **Insights**; a colleague may choose not eligible or select low, mid or high, with an optional note. Only a confirmed eligible choice creates an issued record in **Rewards**; ineligible submissions do not appear there. The eligible decision records one simulated email follow-up, while every submission receives the same generic, email-formatted acknowledgement before analysis. Eligibility decisions are recorded once per submission. The follow-up is not sent to an external email inbox.

"Sufficient detail" requires all four checks: a supported product/service aspect, an opinion or explicit serious incident, at least eight words, and a specific time/place/person/item reference. Detail gates minor-complaint ticket creation, not major/serious or loyalty incentive eligibility. "Genuine" is a heuristic/model signal, not proof that an incident or customer identity is authentic.

## Output Consistency

- A low rating must not reverse clearly positive wording. Rating/text disagreement requires review.
- Positive and negative clauses remain separate; mixed feedback requires review.
- Serious incidents need contextual evidence. Glass doors or "no refund needed" alone do not establish harm.
- Explicit illness after food, undeclared allergens, injuries, discrimination and double charges remain serious concerns.
- Trained aspects require both a keyword match and aspect-presence model support. A checkout location is not automatically a checkout complaint.
- Model-category overrides and low confidence require review. Rule overrides do not artificially raise the model confidence score.
- Customer replies do not claim that a person has been contacted, a refund granted or an incentive transferred.

The model remains a TF-IDF/logistic-regression model trained on synthetic feedback. These safeguards do not prove real-world accuracy or cover every negation, implicit aspect or sarcastic statement. Human-reviewed retail evaluation data is still required; the regression tests are not a production accuracy benchmark.

## Store Selection and Availability

The fixed store IDs are `marble-arch`, `stratford-city`, `bluewater` and `unspecified`. Customer and staff dropdowns start with that catalogue and refresh it from `GET /api/stores`. If the API is offline, the catalogue remains selectable, but submissions cannot be saved and the UI must show an error instead of a success confirmation.

The API requires a working MongoDB connection. Set `MONGODB_URI` and `MONGODB_DATABASE` in the local backend environment file before starting the FastAPI task. Staff credentials are stored as Argon2 password hashes in the separate `staff_users` collection; session tokens are stored as hashes in `staff_sessions`.

## Verification

From the workspace root, without activating the virtual environment:

```powershell
& 'feedback-reward-poc/.venv/Scripts/python.exe' -c "import sys,pytest; sys.path.insert(0,'feedback-reward-poc/backend'); sys.exit(pytest.main(['feedback-reward-poc/backend/tests/test_triage.py','feedback-reward-poc/backend/tests/test_train_absa.py','-q']))"
npm --prefix feedback-reward-poc/frontend run build
```

The route tests use isolated test dependencies rather than live database credentials. Browser checks of mocked staff data must not be described as proof of live persistence.