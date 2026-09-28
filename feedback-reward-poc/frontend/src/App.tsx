import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  ArrowRight,
  Bell,
  ChartNoAxesCombined,
  Check,
  CircleCheck,
  CircleMinus,
  Clock3,
  ClipboardCheck,
  FlaskConical,
  Gift,
  LoaderCircle,
  MessageSquareText,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Ticket,
} from 'lucide-react'
import './App.css'
import Analytics from './Analytics'
import ClosedLoop from './FeedbackResolutionHub'
import TicketWorkflow from './TicketWorkflow'
import CustomerFeedbackForm from './CustomerFeedbackForm'
import { stores, useCaseNotifications } from './caseApi'

type Prediction = {
  feedbackId: string
  feedback: string
  storeId: string
  store: { name: string; location: string }
  loyalCustomer: boolean
  createdAt: number
  updatedAt: number
  revision: number
  sentiment: 'Positive' | 'Neutral' | 'Negative'
  sentimentConfidence: number
  genuineFeedback: 'Yes' | 'No'
  genuineConfidence: number
  rewardEligible: boolean
  reason: string
  category: 'ignored' | 'compliment' | 'major_compliment' | 'minor_complaint' | 'serious_complaint' | 'needs_clarification' | 'suggestion'
  ticketRequired: boolean
  incentiveTier: 'none' | 'tier_based' | 'high'
  rewardDecision: 'eligible' | 'not_eligible' | 'pending'
  customerResponse: string
  clarificationQuestions: string[]
  ticket: {
    id: string
    feedback: string
    category: 'minor_complaint' | 'serious_complaint'
    rewardDecision: 'eligible' | 'not_eligible' | 'pending'
    priority: 'normal' | 'priority'
    status: 'open'
    createdAt: string
  } | null
}

const categoryLabels = {
  ignored: 'Ignored',
  compliment: 'Minor compliment',
  major_compliment: 'Major compliment',
  minor_complaint: 'Minor complaint',
  serious_complaint: 'Serious complaint',
  needs_clarification: 'Awaiting Colleague Review',
  suggestion: 'Store improvement suggestion',
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
  { label: 'Baby clothes compliment', text: 'Baby Clothes are lovely quality and wash well, bought loads for my newborn' },
  { label: 'Payment complaint', text: 'The checkout charged twice for my order yesterday and I lost money.' },
  { label: 'Needs review', text: 'The store is unsafe.' },
]

function isPrediction(value: unknown): value is Prediction {
  if (!value || typeof value !== 'object') return false
  const result = value as Record<string, unknown>
  const ticket = result.ticket as Record<string, unknown> | null
  const store = result.store as Record<string, unknown> | null
  const complaint = ['minor_complaint', 'serious_complaint'].includes(String(result.category))
  const validTicket = result.ticketRequired === true ? (
    complaint &&
    ticket !== null && typeof ticket === 'object' &&
    typeof ticket.id === 'string' && /^[0-9a-f-]{36}$/i.test(ticket.id) &&
    typeof ticket.feedback === 'string' &&
    ticket.category === result.category &&
    ticket.rewardDecision === result.rewardDecision &&
    ticket.priority === (result.category === 'serious_complaint' ? 'priority' : 'normal') &&
    ticket.status === 'open' && typeof ticket.createdAt === 'string' &&
    Number.isFinite(Date.parse(ticket.createdAt))
  ) : ticket === null
  return (
    typeof result.feedbackId === 'string' && /^[0-9a-f-]{36}$/i.test(result.feedbackId) &&
    typeof result.feedback === 'string' && typeof result.storeId === 'string' &&
    !!store && typeof store.name === 'string' && typeof store.location === 'string' &&
    typeof result.loyalCustomer === 'boolean' &&
    ['createdAt', 'updatedAt', 'revision'].every(key => typeof result[key] === 'number' && Number.isFinite(result[key]) && result[key] >= 0) &&
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
    result.rewardEligible === (result.rewardDecision === 'eligible') &&
    ['eligible', 'not_eligible', 'pending'].includes(String(result.rewardDecision)) &&
    Object.hasOwn(categoryLabels, String(result.category)) &&
    typeof result.customerResponse === 'string' &&
    Array.isArray(result.clarificationQuestions) &&
    result.clarificationQuestions.every(question => typeof question === 'string' && question.length > 0) &&
    typeof result.ticketRequired === 'boolean' &&
    ['none', 'tier_based', 'high'].includes(String(result.incentiveTier)) &&
    validTicket && typeof result.reason === 'string'
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

function currentRoute() {
  const [target, caseId = ''] = window.location.hash.slice(1).split('/')
  const page = target === 'closed-loop' ? 'resolution-hub' : ['feedback', 'insights', 'resolution-hub'].includes(target) ? target : 'customer'
  return { page, caseId }
}

function mergeRecords(current: Prediction[], incoming: Prediction[]) {
  const records = new Map(current.map(record => [record.feedbackId, record]))
  for (const record of incoming) {
    const previous = records.get(record.feedbackId)
    if (!previous || previous.revision <= record.revision) records.set(record.feedbackId, record)
  }
  return [...records.values()].sort((left, right) => right.createdAt - left.createdAt || right.feedbackId.localeCompare(left.feedbackId))
}

function App() {
  const [route, setRoute] = useState(currentRoute)
  const page = route.page
  const { notifications, error: notificationError, refresh: refreshNotifications } = useCaseNotifications()
  const newest = notifications.items.find(item => !item.is_read)
  const [records, setRecords] = useState<Prediction[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const historySequence = useRef(0)
  useEffect(() => {
    if (page === 'customer') return
    const controller = new AbortController()
    void loadHistory(null, controller.signal)
    return () => controller.abort()
  }, [page])
  useEffect(() => {
    const navigate = () => setRoute(currentRoute())
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  const [feedback, setFeedback] = useState(examples[0].text)
  const [loyalCustomer, setLoyalCustomer] = useState(false)
  const [storeId, setStoreId] = useState('unspecified')
  const [result, setResult] = useState<Prediction | null>(null)
  const [submittedFeedback, setSubmittedFeedback] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [ticketUpdated, setTicketUpdated] = useState(false)
  const inFlight = useRef(false)
  const submissionId = useRef<string | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const valid = /\p{L}/u.test(feedback.trim())

  async function loadHistory(cursor: string | null = null, signal?: AbortSignal) {
    const sequence = ++historySequence.current
    setHistoryLoading(true)
    setHistoryError('')
    try {
      const response = await fetch(`/api/feedback${cursor ? `?before=${encodeURIComponent(cursor)}` : ''}`, { signal })
      if (!response.ok) throw new Error('Saved feedback is unavailable. Check MongoDB and retry.')
      const history = await response.json()
      if (!Array.isArray(history.items) || !history.items.every(isPrediction) ||
          !(history.nextCursor === null || typeof history.nextCursor === 'string')) throw new Error('The server returned invalid saved feedback.')
      if (sequence !== historySequence.current || signal?.aborted) return
      setRecords(current => mergeRecords(current, history.items))
      setNextCursor(history.nextCursor)
    } catch (caught) {
      if (sequence === historySequence.current && !signal?.aborted) setHistoryError(caught instanceof Error ? caught.message : 'Unable to load saved feedback.')
    } finally {
      if (sequence === historySequence.current && !signal?.aborted) setHistoryLoading(false)
    }
  }

  function openRecord(identity: string) {
    if (inFlight.current) return
    const saved = records.find(record => record.feedbackId === identity)
    if (!saved) return
    changeFeedback(saved.feedback)
    setStoreId(saved.storeId)
    setLoyalCustomer(saved.loyalCustomer)
    setSubmittedFeedback(saved.feedback)
    setResult(saved)
    submissionId.current = saved.revision === 0 ? saved.feedbackId : null
    setTicketUpdated(saved.revision > 0)
    window.location.hash = '#feedback'
  }

  function changeFeedback(value: string) {
    submissionId.current = null
    setFeedback(value)
    setResult(null)
    setSubmittedFeedback('')
    setError('')
  }

  async function analyse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (inFlight.current || !valid) return
    inFlight.current = true
    setLoading(true)
    setError('')
    setResult(null)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 20000)
    submissionId.current ??= crypto.randomUUID()
    try {
      const response = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback: feedback.trim(), submissionId: submissionId.current, loyalCustomer, storeId }),
        signal: controller.signal,
      })
      if (!response.ok) {
        if (response.status === 503) {
          const problem = await response.json().catch(() => null)
          throw new Error(problem?.detail?.startsWith('Feedback storage unavailable')
            ? 'Feedback could not be confirmed as saved. Check MongoDB and retry.'
            : problem?.detail?.startsWith('Ticket storage unavailable')
            ? 'Ticket storage is unavailable. Please retry; no ticket confirmation was received.'
            : 'Models are unavailable. Train both models and restart the backend.')
        }
        if (response.status === 422)
          throw new Error(
            'Enter feedback containing letters, up to 5,000 characters.',
          )
        if ([404, 409].includes(response.status)) {
          const problem = await response.json().catch(() => null)
          throw new Error(typeof problem?.detail === 'string' ? problem.detail : 'The ticket could not be updated. Your previous feedback has been kept.')
        }
        throw new Error(
          'Analysis is unavailable. Check that the FastAPI backend is running and try again.',
        )
      }
      const prediction: unknown = await response.json()
      if (!isPrediction(prediction))
        throw new Error(
          'The server returned an unexpected response. Please try again.',
        )
      setSubmittedFeedback(prediction.feedback)
      setTicketUpdated(false)
      setResult(prediction)
      setRecords(current => mergeRecords(current, [prediction]))
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
        <a className="brand" href="#customer" aria-label="Customer feedback home">
          <span className="brand-mark">
            <MessageSquareText size={21} />
          </span>
          Feedback <span className="brand-divider">/</span>{' '}
          <span className="brand-subtitle">Innovation lab</span>
        </a>
        <nav className="perspective-navigation" aria-label="Perspective navigation">
          <a href="#customer" aria-current={page === 'customer' ? 'page' : undefined}><MessageSquareText size={17} />Customer Perspective</a>
          <div className="colleague-navigation">
            <a href="#feedback" aria-current={page !== 'customer' ? 'page' : undefined}><ClipboardCheck size={17} />Store Colleague Perspective</a>
            <a className="notification-bell" href={newest ? `#resolution-hub/${newest.case_id}` : '#resolution-hub'} aria-label={`New feedback notifications: ${notifications.unread_count}`} title={notificationError || 'New feedback notifications'}><Bell className="notification-icon" size={19} />
              <span className="notification-count" data-testid="notification-count" aria-live="polite">{notifications.unread_count}</span>
            </a>
          </div>
        </nav>
        <span className="poc-badge">
          <FlaskConical size={14} /> Proof of concept
        </span>
      </header>
      <main>
        <div hidden={page !== 'customer'}><CustomerFeedbackForm onSubmitted={refreshNotifications} /></div>
        {page !== 'customer' && <nav className="page-nav colleague-tabs" aria-label="Colleague navigation">
          <a href="#feedback" aria-current={page === 'feedback' ? 'page' : undefined}><MessageSquareText size={17} />Feedback</a>
          <a href="#insights" aria-current={page === 'insights' ? 'page' : undefined}><ChartNoAxesCombined size={17} />Insights</a>
          <a href="#resolution-hub" aria-current={page === 'resolution-hub' ? 'page' : undefined}><ClipboardCheck size={17} />Feedback Resolution Hub</a>
        </nav>}
        {page !== 'customer' && notificationError && <p className="error" role="alert">{notificationError}</p>}
        {(page === 'resolution-hub' || page === 'feedback') && <ClosedLoop key={page} compact={page === 'feedback'} revision={notifications.revision} requestedCaseId={route.caseId} onChanged={refreshNotifications} />}
        {page === 'customer' || page === 'resolution-hub' ? null : page === 'insights' ? <Analytics records={records}
          loading={historyLoading} error={historyError} hasMore={nextCursor !== null} busy={loading}
          onRefresh={() => void loadHistory()} onLoadMore={() => void loadHistory(nextCursor)} onOpen={openRecord} /> : <>
        <h2 className="analysis-section-heading">Feedback analysis</h2>
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
              <label htmlFor="feedback-store">Feedback store</label>
              <select id="feedback-store" value={storeId} disabled={loading} onChange={event => { setStoreId(event.target.value); changeFeedback(feedback) }}>
                {stores.map(store => <option key={store.id} value={store.id}>{store.name}</option>)}
              </select>
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
              <label className="loyalty-input"><input type="checkbox" checked={loyalCustomer} disabled={loading} onChange={event => { setLoyalCustomer(event.target.checked); changeFeedback(feedback) }} />Sparks Customer (POC profile)</label>
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
                <h3>Feedback recognition</h3>
                <p>
                  Service recovery, exceptional appreciation and Sparks Customers.
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
                  <p className="saved-feedback">Saved · {result.store.name} · {result.loyalCustomer ? 'Sparks Customer' : 'Non-Sparks Customer'}</p>
                  <div
                    className={`decision ${result.rewardDecision === 'pending' ? 'pending' : result.rewardEligible ? 'eligible' : 'not-eligible'}`}
                  >
                    <div className="decision-icon">
                      {result.rewardDecision === 'pending' ? <Clock3 size={27} /> : result.rewardEligible ? (
                        <CircleCheck size={27} />
                      ) : (
                        <CircleMinus size={27} />
                      )}
                    </div>
                    <div>
                      <span>REWARD RECOMMENDATION</span>
                      <h3>
                        {result.rewardDecision === 'pending' ? 'Awaiting Colleague Review' : result.rewardEligible ? 'Eligible' : 'Not eligible'}
                      </h3>
                    </div>
                    <span className="decision-tag">
                      COLLEAGUE REVIEW REQUIRED
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
                        label="Sentiment model support"
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
                    <h3>{categoryLabels[result.category]}</h3>
                    <p>{result.reason}</p>
                  </div>
                  {result.incentiveTier !== 'none' && <div className="explanation"><h3>Incentive recommendation</h3><p>{result.incentiveTier === 'high' ? 'High-tier Sparks incentive' : 'Standard reward'} · Points undecided · Not issued</p></div>}
                  {result.customerResponse && <div className="explanation customer-response">
                    <h3>Customer Communication</h3>
                    <p>Thank you for your feedback. Your submission has been reviewed and the case has been updated.</p>
                  </div>}
                  {result.ticket && <section className="ticket-details" aria-label="Complaint ticket">
                    <h3><Ticket size={17} /> {ticketUpdated ? 'Ticket updated' : 'Ticket opened'}</h3>
                    <dl>
                      <div><dt>Reference</dt><dd>{result.ticket.id}</dd></div>
                      <div><dt>Priority</dt><dd>{result.ticket.priority === 'priority' ? 'Priority attention' : 'Normal'}</dd></div>
                      <div><dt>Created</dt><dd>{new Date(result.ticket.createdAt).toLocaleString()}</dd></div>
                    </dl>
                    <TicketWorkflow key={result.ticket.id} ticketId={result.ticket.id} busy={loading} />
                  </section>}
                  <div className="feedback-quote">
                    <h3>Feedback analysed</h3>
                    <blockquote>{submittedFeedback}</blockquote>
                  </div>
                  <p className="confidence-note">
                    Model support is not verified sentiment accuracy. Rewards are recommendations only.
                  </p>
                </div>
              )}
            </div>
          </section>
        </div>
        </>}
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
