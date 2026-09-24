# Customer Feedback Reward Recommendation System

A local showcase POC: React + TypeScript + Vite, FastAPI, and two independently trained scikit-learn classifiers. No external AI service or API key is required. This is not a production reward system and does not issue rewards.

## Flow and business rules

```text
Customer feedback -> Sentiment model -> Positive / Neutral / Negative
                  -> Genuine-feedback model + decision rules -> Yes / No
                  -> Response policy -> Category / Ticket requirement
                  -> Incentive recommendation -> Eligible / Not eligible / Pending
```

Both models train and predict entirely locally with scikit-learn: no Hugging Face, pretrained-model download, PyTorch, or external AI call. Sentiment uses word unigram/bigram TF-IDF + Logistic Regression. Genuine feedback uses a feature union of word unigram/bigram and character 3-5-gram TF-IDF + Logistic Regression. Both use balanced class weights and a fixed random seed. Saved joblib files include their fitted vectorizers. The genuine classifier sees feedback text, not sentiment.

Reward eligibility is separate from the genuine-feedback label and sentiment. The POC response policy is:

| Feedback | Response | Incentive recommendation |
| --- | --- | --- |
| Minor compliment | Thank with context; close the loop | None |
| Gibberish | Ignore; no reply or ticket | None |
| Minor complaint | Apologise; open a ticket when details suffice, otherwise request details | None by default |
| Serious complaint | Apologise; open a priority ticket for review | Tier-based when sufficiently detailed; otherwise pending |
| Major compliment | Thank the customer for specific exceptional service recognition | Tier-based |
| Loyal customer with genuine, specific feedback | Respond to the underlying feedback | High tier, overriding the default incentive |

`incentiveTier` is `none`, `tier_based`, or `high`. Amounts, tier definitions and fulfilment are deliberately undecided. Loyalty is a manually selected POC profile flag, not an authenticated customer entitlement. The live API does not assign colleagues or contact customers; the Closed Loop page illustrates those future steps with sample cases.

The bounded English phrase rules in `backend/triage.py` consider serious issues first, then complaints and compliments. Major compliments require recognised exceptional-service wording, meaningful detail, a product/service subject, and a genuine label. Explicit service recovery can be recognised without hiding a separate complaint. Loyalty only overrides eligibility for classified, meaningful feedback with a genuine label; gibberish is never rewarded just because the loyalty flag is selected. Complex negation, novel wording, severity, and major-versus-minor distinctions still need human review.

The genuine classifier architecture and its original safeguards are unchanged: contextual stock feedback can set genuine to Yes; bare availability claims set it to No; other feedback uses a minimum-detail gate and the model. A genuine stock complaint does not automatically earn an incentive. The genuine model has been retrained locally with the expanded synthetic supplement described below. Sentiment and the six-category reward policy are unchanged.

This check addresses a real model failure: text with no TF-IDF features such as "Hi" previously defaulted to Yes from the classifier's intercept. Stopwords alone or a repeated known keyword could also cause false approvals. The safeguard uses distinct supported content words, not just message length. It is a heuristic, not semantic understanding: useful unfamiliar wording can be rejected and combinations of recognised keywords can still fool it. Better labelled data and independent evaluation remain necessary.

The reason is a transparent rule-based explanation of the prediction, not an LLM explanation or independently verified assessment of actionability. `genuine_feedback` is a synthetic proxy for usefulness, not proof that a person or statement is authentic.

## Structure

```text
feedback-reward-poc/
  frontend/
    src/App.tsx                Feedback form, request lifecycle, results
    src/App.css                Responsive workspace styling
    src/ClosedLoop.tsx          Sample store cases, history and demo resolution
    src/ClosedLoop.css          Closed Loop responsive layout
    src/index.css              Typography and design tokens
    src/main.tsx               React entry point
    index.html
    vite.config.ts             /api proxy to FastAPI
    package.json
    package-lock.json
    playwright.config.ts
    tests/app.spec.ts          Live browser tests and screenshot capture
  backend/
    data/customer_feedback_training_data_300.csv
    data/genuine_feedback_synthetic.csv  Synthetic supplement, not real customer data
    training.py                Shared validation, training, evaluation
    train_sentiment.py
    train_genuine.py
    predict.py                 Model loading and reward rule
    triage.py                  Response and incentive policy
    tickets.py                 SQLite-backed local complaint tickets
    main.py                    FastAPI endpoints
    requirements.txt
    pytest.ini
    tests/test_api.py
    sentiment_model.pkl        Generated by training
    genuine_model.pkl          Generated by training
    sentiment_metrics.json     Generated evaluation report
    genuine_feedback_metrics.json
  docs/screenshots/
    desktop.png
    mobile.png
  README.md
```

## Setup on Windows PowerShell

Prerequisites: Python 3.11+ (tested with 3.13), Node.js 22.12+ or a supported newer LTS, and npm. Run these commands from this project folder. The CSV has already been copied into `backend/data`; the original is unchanged.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe backend/train_sentiment.py
.\.venv\Scripts\python.exe backend/train_genuine.py
npm --prefix frontend ci
```

No virtual-environment activation is required. Both model files are created beside the scripts regardless of the working directory. To train on another CSV, pass `--data "C:\path\dataset.csv"` to each script. Restart FastAPI after retraining. Only load trusted, locally generated joblib files; pickle-based files can execute code.

The default genuine training command combines the original CSV with `backend/data/genuine_feedback_synthetic.csv`. Custom genuine datasets need only `feedback_text,genuine_feedback`, with labels `Yes` (specific/useful) and `No` (generic/insufficiently specific), not proof of authenticity. A custom `--data` file is used alone unless `--supplement` is explicitly supplied. Exact normalized duplicates are removed, conflicting genuine labels are rejected, and at least four unique examples per class are required to create the split, not to establish reliability. The default supplement contains 140 assistant-authored synthetic examples (70 Yes, 70 No) and requires human label review before any real deployment.

The latest expansion adds 60 examples: 30 specific/useful and 30 generic/insufficiently specific. Scenarios cover product performance, service recovery, accessibility, payment issues, facilities, vague praise, reward requests and nonsense. A few examples mention the three demo stores, paired with location-only and generic store comments labelled No. All such incidents are fictional, not reviews collected from those stores or claims about their service. No websites were scraped. Store names are not a separate model feature or an eligibility rule; their appearance in free text can still influence TF-IDF and needs monitoring. Specific positive feedback can be genuine without earning an incentive. This is a full local refit of TF-IDF and logistic regression, not transformer fine-tuning or a verified production-quality improvement.

```powershell
.\.venv\Scripts\python.exe backend/train_genuine.py --data "C:\path\reviewed_feedback.csv"
```

Terminal 1, from this project folder:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Terminal 2, from this project folder:

```powershell
npm --prefix frontend run dev
```

- App: http://127.0.0.1:5173 (use the URL Vite prints if that port is occupied).
- API documentation: http://127.0.0.1:8000/docs
- Readiness: http://127.0.0.1:8000/health

The frontend sends requests to `/api/predict`; Vite proxies to FastAPI's `/predict`, avoiding cross-origin browser requests. If port 8000 is occupied, choose another API port and update both proxy targets in `frontend/vite.config.ts`. Stop either server with Ctrl+C. Keep both services bound to localhost.

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` and use `python3` to create the environment. Other commands are the same.

## Session analytics

Open **Insights** in the header or visit http://127.0.0.1:5173/#insights. The dashboard records successful, validated predictions submitted in this browser tab, including requests that finish while Insights is open. Failed requests are excluded. It shows sentiment distribution, genuine-feedback and eligibility totals, recent activity in five-minute intervals, and the latest 50 matching feedback entries. Totals include all matching session entries, including repeat submissions.

Time and sentiment filters apply to totals, distribution, and recent feedback; the activity chart always shows the latest 12 five-minute intervals within those filters. The clock refreshes every 15 seconds. Clear history requires confirmation. History stays in memory only and resets on reload or closing the tab; it does not include other users, tabs, API clients, or the training CSV. There is no persistent analytics database or background ingestion. Predictions are not verified authenticity or accuracy.

Screenshots: [Insights desktop](docs/screenshots/analytics-desktop.png), [Insights mobile](docs/screenshots/analytics-mobile.png).

## Closed Loop demo

Open **Closed Loop** in the header or visit http://127.0.0.1:5173/#closed-loop. Seven fictional cases across three stores demonstrate the proposed store QR feedback journey: receipt, colleague alert, apology or thanks, ticket/owner where appropriate, completed action, and customer update. A gibberish sample is counted as ignored without retaining its text or opening a ticket.

Filter by store and status or search case references, customers and feedback. Store totals follow the store filter; the list follows all filters. Resolved cases display **You said / We did**, named colleagues, action histories and simulated customer messages. Minor and major compliments can close through acknowledgement without a complaint ticket. Tier-based and high-tier recommendations never imply an incentive has been issued.

For an interactive demonstration, select **Empty hand-soap dispenser**, choose **Start work (demo)**, enter the completed action and choose **Record resolution (demo)**. The case becomes Resolved, its history and closed-case totals update, and a simulated customer update is recorded. Changes survive navigation within the tab but reset on refresh. Awaiting-details cases cannot be resolved directly.

This page uses in-memory dummy data, separate from live predictions, SQLite tickets and Insights. No QR registration, real colleague alerts, customer contact, identity verification, evidence verification or incentive delivery is implemented. Assignments, callbacks and historical completions in the samples are illustrative only. The resolution button records a demo assertion, not proof that physical work happened.

Screenshots: [Closed Loop desktop](docs/screenshots/closed-loop-desktop.png), [Closed Loop mobile](docs/screenshots/closed-loop-mobile.png).

## Prediction API

`POST /predict`, content type `application/json`:

```json
{ "feedback": "Baby clothes are lovely quality and wash well, bought loads for my newborn", "loyalCustomer": true }
```

Response shape (illustrative probabilities, not a promised output):

```json
{
  "sentiment": "Positive",
  "sentimentConfidence": 0.91,
  "genuineFeedback": "Yes",
  "genuineConfidence": 0.95,
  "rewardEligible": true,
  "category": "compliment",
  "rewardDecision": "eligible",
  "incentiveTier": "high",
  "ticketRequired": false,
  "ticket": null,
  "customerResponse": "Thank you for your kind feedback about our baby clothes.",
  "reason": "A loyal customer provided genuine, specific feedback; a high-tier incentive is recommended."
}
```

Confidence is the displayed class's `predict_proba` value in [0, 1]. When a genuine-feedback rule sets No or Yes, genuine confidence remains the original model's probability for that displayed label, which may be below 50%; it is not fabricated certainty in the rule. The reason explains the response/incentive policy, not the model internals. The UI rounds probabilities to percentages. These values are not calibrated accuracy or severity confidence. Actual output depends on the trained data, including labels for mixed feedback.

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/predict -Method Post -ContentType 'application/json' -Body '{"feedback":"The checkout queue is very long between 5 PM and 6 PM."}'
```

Input must be a string of 1-5,000 characters containing at least one letter. Optional `loyalCustomer` is a strict boolean, default false. Optional `submissionId` is a UUID; the UI reuses it on retries and resets it when feedback or loyalty changes. Blank, numeric-only, malformed, oversized, and extra-field requests return 422. Unavailable models return 503 with training instructions. `/health` reports `modelsLoaded`; its HTTP 200 indicates API reachability, not necessarily model readiness.

When `ticketRequired` is true, the API stores the complaint text and ticket metadata in local `backend/tickets.sqlite3` (or `FEEDBACK_TICKETS_DB`). `GET /tickets/{uuid}` retrieves it after a restart. Ticket fields are `id`, `feedback`, `category`, `rewardDecision`, `priority`, `status` (open) and `createdAt`. Retries reuse the ticket; conflicting reuse returns 409. Storage failures return 503 rather than a false ticket confirmation. Non-ticket feedback is not stored by the API. Tickets have no authentication, retention workflow, assignment or resolution API; keep this local and use synthetic feedback only. The Closed Loop page is not a view of this database.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm --prefix frontend run build
npm --prefix frontend run lint
```

Train both models before running tests. Tests cover model safeguards, the six-category incentive policy, loyalty, detail-gated tickets, retry persistence, response fields, probabilities, invalid requests, readiness, and unavailable models.

With both servers running, run the repeatable browser checks:

```powershell
npm --prefix frontend run test:e2e
```

On Windows the tests use installed Microsoft Edge. On other platforms they use Playwright Chromium; install it from `frontend` with `npx playwright install chromium`. To use Chromium on Windows, install it the same way and set `$env:PLAYWRIGHT_CHANNEL = 'chromium'` before running the tests. The tests expect the frontend on port 5173; update `baseURL` in `frontend/playwright.config.ts` if necessary.

The browser tests exercise the real API, verify reward examples, greeting/nonsense rejection, detailed appreciation with and without greetings, generic stock rejection versus contextual stock acceptance, invalid-input disabling, loading locks, simulated 503 recovery, and layouts at 320, 390, 768, and 1440 pixels. They also verify session analytics, sentiment and time filters, navigation, history clearing, reload reset, failed-request exclusion, and updates while Insights is open. They regenerate the screenshots below. Backend tests additionally verify local training and model reload with network connections disabled, training-data validation, duplicate isolation, and expanded feedback examples. The backend test runner emits two dependency deprecation warnings.

For a local production-build preview, keep FastAPI running:

```powershell
npm --prefix frontend run build
npm --prefix frontend run preview
```

This preview also proxies `/api`. A deployed static build would need its own reverse proxy; deployment, authentication, rate limiting, and reward fulfilment are outside this POC.

## Dataset quality and limitations

The supplied 300-row CSV has only **25 unique feedback texts**. **10 text groups have conflicting sentiment labels**; for example, short generic comments occur under different sentiments. No labels were silently corrected. Genuine/reward labels agree for all rows.

Sentiment retains its original grouped holdout (89 rows), with 21.3% accuracy. Genuine training combines 300 original rows and 140 synthetic supplemental rows, deduplicating 440 rows to **165 unique texts**. A fixed-seed stratified split uses 123 texts for training and 42 for evaluation. TF-IDF is fitted only on the training partition during evaluation; a fresh final genuine model is then fitted on all 165 unique texts for this demo.

| Genuine classifier | Synthetic holdout accuracy | Macro F1 |
| --- | ---: | ---: |
| Word + character TF-IDF | 92.9% | 92.9% |
| Word-only baseline on the same split | 92.9% | 92.9% |

Genuine recall is 90.9% (20/22); not-genuine recall is 95.0% (19/20). Character features have **not** demonstrated an accuracy gain over the word-only baseline on this split. The earlier 74.1% accuracy used a different 27-example holdout; these scores are not directly comparable because the dataset and split changed. Full metrics and held-out predictions are in `backend/genuine_feedback_metrics.json`. The three held-out errors and the tiny synthetic sample still matter; this is not evidence of real-world accuracy.

The supplement adds clothing, returns, payments, delivery, accessibility, and service examples, plus greetings, nonsense, and long generic praise. It broadens vocabulary but is assistant-authored synthetic data, not independently reviewed customer evidence. Related scenarios may occur across the split. Human-labelled, independently held-out real feedback is still needed. Passing regressions after the final refit is **not** proof of unseen-data accuracy.

These scores evaluate the raw classifiers, not the combined model and decision rules. The stock rule uses an explicit product lexicon and phrase patterns, not general semantic understanding. The minimum-detail gate still requires some known vocabulary: genuinely useful unfamiliar feedback can still be rejected. Unfamiliar products, typos, complex negation, and keyword combinations remain limitations. Probabilities are not calibrated accuracy estimates.

Do not use this to make real reward decisions. Improve unique examples and label consistency, collect representative held-out data, assess per-class performance and calibration, and include human review before considering a real pilot. No inference-time duplicate detection is implemented; grouped evaluation only prevents duplicate leakage in measurement.

## Mockup and showcase walkthrough

Actual local captures: [Desktop screenshot](docs/screenshots/desktop.png) and [Mobile screenshot](docs/screenshots/mobile.png).

![Desktop recommendation view](docs/screenshots/desktop.png)

Desktop: a white header with a feedback icon and POC badge, followed by the project title and four compact workflow stages. A divided, two-column workspace places the textarea, sample selector, analyse button, and clear icon on the left. The right-hand results panel begins with an empty state, then shows an eligibility band, sentiment label, genuine label, two confidence bars, decision reason, and the exact submitted feedback. Green indicates eligibility; negative sentiment uses coral independently. A disclaimer remains below the workspace.

Mobile: the input and results stack vertically, the workflow becomes a two-column grid, and long feedback wraps inside a scrollable quotation. Controls have focus indicators and accessible labels. Loading is announced, duplicate submission is blocked, errors appear inline, and editing invalidates any previous result. Google Fonts are optional; local fallback fonts keep the UI usable offline.

Suggested showcase captures:

1. **Useful negative feedback:** select Store improvement, analyse, capture Negative / Yes / Eligible.
2. **Generic praise:** select Generic praise, analyse, capture No / Not eligible regardless of sentiment.
3. **Minor compliment:** select Helpful service, analyse, capture Positive / Yes / Not eligible. Enable the POC loyalty flag to demonstrate a high-tier recommendation for genuine feedback.
4. **Mobile result:** repeat Store improvement at a 390px viewport.

## Future enhancements

Future versions could connect actual store QR registration, colleague alerts, assignment, customer conversations, evidence-backed resolution, verified loyalty profiles and incentive distribution. Tier amounts and fulfilment rules remain future work; current tier labels are recommendations only. Additional prerequisites include better labels, independent evaluation, calibrated probabilities, privacy controls, authenticated access, duplicate/fraud prevention, monitoring, and a human approval step.