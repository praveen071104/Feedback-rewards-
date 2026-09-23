import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  ArrowRight,
  Check,
  CircleCheck,
  CircleMinus,
  FlaskConical,
  Gift,
  LoaderCircle,
  MessageSquareText,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import './App.css'

type Prediction = {
  sentiment: 'Positive' | 'Neutral' | 'Negative'
  sentimentConfidence: number
  genuineFeedback: 'Yes' | 'No'
  genuineConfidence: number
  rewardEligible: boolean
  reason: string
}

const examples = [
  {
    label: 'Store improvement',
    text: 'The store lighting is too dim and causes eye strain while shopping.',
  },
  {
    label: 'Helpful service',
    text: 'The colleague at the till was very helpful and resolved my issue quickly.',
  },
  {
    label: 'Mixed experience',
    text: 'The meal deal selection is great but sandwiches are often out of stock by lunchtime.',
  },
  { label: 'Generic praise', text: 'Good' },
]

function isPrediction(value: unknown): value is Prediction {
  if (!value || typeof value !== 'object') return false
  const result = value as Record<string, unknown>
  return (
    ['Positive', 'Neutral', 'Negative'].includes(String(result.sentiment)) &&
    ['Yes', 'No'].includes(String(result.genuineFeedback)) &&
    ['sentimentConfidence', 'genuineConfidence'].every(
      (key) =>
        typeof result[key] === 'number' &&
        Number.isFinite(result[key]) &&
        result[key] >= 0 &&
        result[key] <= 1,
    ) &&
    typeof result.rewardEligible === 'boolean' &&
    result.rewardEligible === (result.genuineFeedback === 'Yes') &&
    typeof result.reason === 'string'
  )
}

function Confidence({ label, value }: { label: string; value: number }) {
  const percent = Math.round(value * 100)
  return (
    <div className="confidence">
      <div>
        <span>{label}</span>
        <strong>{percent}%</strong>
      </div>
      <div
        className="meter"
        role="meter"
        aria-label={label}
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

function App() {
  const [feedback, setFeedback] = useState(examples[0].text)
  const [result, setResult] = useState<Prediction | null>(null)
  const [submittedFeedback, setSubmittedFeedback] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const inFlight = useRef(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const valid = /\p{L}/u.test(feedback.trim())

  function changeFeedback(value: string) {
    setFeedback(value)
    setResult(null)
    setSubmittedFeedback('')
    setError('')
  }

  async function analyse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!valid || inFlight.current) return
    inFlight.current = true
    setLoading(true)
    setError('')
    setResult(null)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 20000)
    try {
      const response = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback: feedback.trim() }),
        signal: controller.signal,
      })
      if (!response.ok) {
        if (response.status === 503)
          throw new Error(
            'Models are unavailable. Train both models and restart the backend.',
          )
        if (response.status === 422)
          throw new Error(
            'Enter feedback containing letters, up to 5,000 characters.',
          )
        throw new Error(
          'Analysis is unavailable. Check that the FastAPI backend is running and try again.',
        )
      }
      const prediction: unknown = await response.json()
      if (!isPrediction(prediction))
        throw new Error(
          'The server returned an unexpected response. Please try again.',
        )
      setSubmittedFeedback(feedback.trim())
      setResult(prediction)
    } catch (caught) {
      setError(
        caught instanceof Error && caught.name === 'AbortError'
          ? 'The request timed out. Please try again.'
          : caught instanceof TypeError
            ? 'Cannot reach the backend. Check your connection and try again.'
            : caught instanceof Error
              ? caught.message
              : 'Analysis failed. Please try again.',
      )
    } finally {
      clearTimeout(timeout)
      inFlight.current = false
      setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Customer feedback home">
          <span className="brand-mark">
            <MessageSquareText size={21} />
          </span>
          Feedback <span className="brand-divider">/</span>{' '}
          <span className="brand-subtitle">Innovation lab</span>
        </a>
        <span className="poc-badge">
          <FlaskConical size={14} /> Proof of concept
        </span>
      </header>
      <main>
        <div className="page-heading">
          <div>
            <p className="eyebrow">CUSTOMER EXPERIENCE</p>
            <h1>
              Customer Feedback
              <br />
              <span>Reward Recommendation System</span>
            </h1>
          </div>
          <div className="edition">
            <span className="status-dot" /> SYNTHETIC DATASET
            <span className="edition-number">EXPERIMENT 01 / 300 RECORDS</span>
          </div>
        </div>
        <ol className="workflow" aria-label="Analysis stages">
          <li className="current">
            <span className="step-number">01</span> Customer feedback
          </li>
          <ArrowRight aria-hidden="true" size={16} />
          <li>
            <span className="step-number">02</span> Sentiment analysis
          </li>
          <ArrowRight aria-hidden="true" size={16} />
          <li>
            <span className="step-number">03</span> Genuine feedback
          </li>
          <ArrowRight aria-hidden="true" size={16} />
          <li>
            <span className="step-number">04</span> Reward decision
          </li>
        </ol>
        <div className="workspace">
          <section className="input-section" aria-labelledby="feedback-heading">
            <div className="section-heading">
              <h2 id="feedback-heading">
                <MessageSquareText size={19} /> Feedback input
              </h2>
              <span className="section-index">01 / INPUT</span>
            </div>
            <form onSubmit={analyse}>
              <label htmlFor="feedback">Customer feedback</label>
              <div className="textarea-wrap">
                <textarea
                  id="feedback"
                  ref={inputRef}
                  value={feedback}
                  onChange={(event) => changeFeedback(event.target.value)}
                  maxLength={5000}
                  disabled={loading}
                  placeholder="Enter customer feedback..."
                  required
                  aria-describedby="character-count"
                />
                <span id="character-count">
                  {feedback.length.toLocaleString()} / 5,000
                </span>
              </div>
              <div className="form-actions">
                <button
                  type="submit"
                  className="primary-button"
                  disabled={!valid || loading}
                >
                  {loading ? (
                    <LoaderCircle className="spin" size={18} />
                  ) : (
                    <Sparkles size={18} />
                  )}
                  {loading ? 'Analysing feedback...' : 'Analyse feedback'}
                  {!loading && <ArrowRight size={18} />}
                </button>
                <button
                  type="button"
                  className="icon-button"
                  title="Clear feedback"
                  aria-label="Clear feedback"
                  disabled={loading || !feedback}
                  onClick={() => {
                    changeFeedback('')
                    inputRef.current?.focus()
                  }}
                >
                  <RotateCcw size={18} />
                </button>
              </div>
              {error && (
                <div className="error" role="alert">
                  <TriangleAlert size={18} />
                  <span>{error}</span>
                </div>
              )}
            </form>
            <div className="examples">
              <label htmlFor="example">Sample feedback</label>
              <select
                id="example"
                value={
                  examples.find((sample) => sample.text === feedback)?.label ??
                  ''
                }
                disabled={loading}
                onChange={(event) => {
                  const sample = examples.find(
                    (item) => item.label === event.target.value,
                  )
                  if (sample) changeFeedback(sample.text)
                }}
              >
                <option value="" disabled>
                  Custom feedback
                </option>
                {examples.map((sample) => (
                  <option key={sample.label} value={sample.label}>
                    {sample.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="principle">
              <ShieldCheck size={20} />
              <div>
                <h3>Value over sentiment</h3>
                <p>
                  Reward eligibility is based on predicted genuine feedback,
                  regardless of sentiment.
                </p>
              </div>
            </div>
          </section>
          <section
            className="result-section"
            aria-labelledby="results-heading"
            aria-busy={loading}
          >
            <div className="section-heading">
              <h2 id="results-heading">
                <Gift size={19} /> Recommendation
              </h2>
              <span className="section-index">02 / RESULTS</span>
            </div>
            <div aria-live="polite" aria-atomic="true">
              {!result ? (
                <div className={`empty-state ${loading ? 'is-loading' : ''}`}>
                  <div className="empty-icon">
                    {loading ? (
                      <LoaderCircle size={31} className="spin" />
                    ) : (
                      <MessageSquareText size={31} />
                    )}
                  </div>
                  <h3>
                    {loading
                      ? 'Analysing feedback'
                      : 'Awaiting feedback analysis'}
                  </h3>
                  <span className="empty-caption">
                    {loading
                      ? 'Processing your recommendation...'
                      : 'No recommendation yet'}
                  </span>
                  <div className="empty-lines" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              ) : (
                <div className="result-content">
                  <div
                    className={`decision ${result.rewardEligible ? 'eligible' : 'not-eligible'}`}
                  >
                    <div className="decision-icon">
                      {result.rewardEligible ? (
                        <CircleCheck size={27} />
                      ) : (
                        <CircleMinus size={27} />
                      )}
                    </div>
                    <div>
                      <span>REWARD RECOMMENDATION</span>
                      <h3>
                        {result.rewardEligible ? 'Eligible' : 'Not eligible'}
                      </h3>
                    </div>
                    <span className="decision-tag">
                      {result.rewardEligible ? 'QUALIFIES' : 'DOES NOT QUALIFY'}
                    </span>
                  </div>
                  <div className="metrics">
                    <div className="metric">
                      <div className="metric-title">
                        Sentiment
                        <span
                          className={`sentiment ${result.sentiment.toLowerCase()}`}
                        >
                          {result.sentiment}
                        </span>
                      </div>
                      <Confidence
                        label="Sentiment confidence"
                        value={result.sentimentConfidence}
                      />
                    </div>
                    <div className="metric">
                      <div className="metric-title">
                        Genuine feedback
                        <span className="genuine-label">
                          {result.genuineFeedback === 'Yes' && (
                            <Check size={15} />
                          )}
                          {result.genuineFeedback}
                        </span>
                      </div>
                      <Confidence
                        label="Genuine confidence"
                        value={result.genuineConfidence}
                      />
                    </div>
                  </div>
                  <div className="explanation">
                    <h3>Decision reason</h3>
                    <p>{result.reason}</p>
                  </div>
                  <div className="feedback-quote">
                    <h3>Feedback analysed</h3>
                    <blockquote>{submittedFeedback}</blockquote>
                  </div>
                  <p className="confidence-note">
                    Confidence is model probability, not verified accuracy.
                  </p>
                </div>
              )}
            </div>
          </section>
        </div>
        <aside className="disclaimer">
          <FlaskConical size={18} />
          <p>
            <strong>Showcase only.</strong> Small synthetic dataset with
            conflicting labels. Recommendations may be inaccurate. No rewards
            are issued.
          </p>
        </aside>
      </main>
      <footer>
        <span>FEEDBACK INTELLIGENCE / POC</span>
        <span>
          TF-IDF + Logistic Regression<span className="footer-dot">/</span>React
          + FastAPI
        </span>
      </footer>
    </div>
  )
}

export default App
