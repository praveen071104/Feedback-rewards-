import { useEffect, useEffectEvent, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowLeft, ArrowRight, Check, CircleMinus, Clock3, LoaderCircle, Mail, RefreshCw, Search, Star, Store } from 'lucide-react'
import { caseApi, decisions, statuses, stores } from './caseApi'
import type { CaseDetail, CasePage, CaseStatus, Decision, Insights, Template } from './caseApi'
import './ClosedLoop.css'
import './CustomerJourney.css'

const storeName = (identity: string) => stores.find(store => store.id === identity)?.name ?? identity
const reference = (identity: string) => identity.slice(0, 8).toUpperCase()
const percent = (value: number) => `${Math.round(value * 100)}%`

export function ColleagueInsights({ insights }: { insights: Insights | null }) {
  if (!insights) return null
  if (!insights.total) return <p className="live-case-summary">No feedback insights are available yet.</p>
  const metrics: [string, string | number][] = [
    ['Total feedback cases', insights.total], ...statuses.map(status => [status, insights.statuses[status] ?? 0] as [string, number]),
    ...decisions.map(decision => [decision === 'Awaiting Colleague Review' ? 'Awaiting Review' : decision, insights.decisions[decision] ?? 0] as [string, number]),
    ['Average star rating', insights.average_rating?.toFixed(1) ?? 'Not available'], ['New feedback', insights.unread_count],
  ]
  return <section className="case-summary" aria-label="Feedback insights">{metrics.map(([label, value]) => <p key={label}><strong>{value}</strong>{label}</p>)}
    <p className="sentiment-summary">{['Positive', 'Neutral', 'Negative'].map(label => `${label}: ${insights.sentiments[label] ?? 0}`).join(' / ')}</p>
  </section>
}

function FeedbackCaseDetail({ item, onSaved, onReload, onNotice }: {
  item: CaseDetail; onSaved: (item: CaseDetail) => void; onReload: () => void; onNotice: (message: string) => void
}) {
  const [status, setStatus] = useState<CaseStatus>(item.case_status)
  const [store, setStore] = useState(item.store_id)
  const [colleague, setColleague] = useState(item.reward_assessment.confirmed_by ?? '')
  const [reason, setReason] = useState(item.reward_assessment.decision_reason ?? '')
  const [note, setNote] = useState('')
  const [template, setTemplate] = useState<Template>(item.reward_assessment.final_decision === 'Reward Eligible' ? 'reward_eligible' : item.reward_assessment.final_decision === 'Not Eligible' ? 'not_eligible' : 'general')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inFlight = useRef(false)
  const operation = useRef<{ signature: string; id: string } | null>(null)
  const assessment = item.reward_assessment

  async function mutate(action: 'review' | 'notify', fields: Record<string, unknown>) {
    if (inFlight.current) return
    inFlight.current = true; setBusy(true); setError(''); onNotice('')
    const signature = JSON.stringify({ action, ...fields, expected_version: item.version })
    if (operation.current?.signature !== signature) operation.current = { signature, id: crypto.randomUUID() }
    try {
      const updated = await caseApi<CaseDetail>(`colleague/feedback-cases/${item.case_id}${action === 'notify' ? '/notify-customer' : ''}`, {
        method: action === 'notify' ? 'POST' : 'PATCH', body: JSON.stringify({ ...fields, operation_id: operation.current.id, expected_version: item.version }),
      })
      onSaved(updated)
      if (action === 'review') {
        setTemplate(updated.reward_assessment.final_decision === 'Reward Eligible' ? 'reward_eligible' : updated.reward_assessment.final_decision === 'Not Eligible' ? 'not_eligible' : 'general')
        setNote('')
      }
      onNotice(action === 'review' ? 'Colleague decision recorded.' : item.customer.email
        ? 'Customer notification email has been sent successfully. POC simulation only; no email was delivered.'
        : 'Customer notification has been recorded. POC simulation only.')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Unable to save. Please retry.') }
    finally { inFlight.current = false; setBusy(false) }
  }

  function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const decision = ((event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value as Decision | undefined
    if (!decision || !colleague.trim() || !reason.trim()) return
    void mutate('review', { case_status: status, store_id: store, final_decision: decision, confirmed_by: colleague, decision_reason: reason, colleague_note: note })
  }

  return <section className="loop-detail case-editor" aria-labelledby="case-title" aria-busy={busy}>
    <div className="case-detail-toolbar"><span className="case-reference">Case {reference(item.case_id)}</span><button className="icon-button" type="button" disabled={busy} title="Reload case" aria-label="Reload case" onClick={() => {
      if (window.confirm('Reload this case? Unsaved changes will be discarded.')) onReload()
    }}><RefreshCw size={17} /></button></div>
    <div className="loop-detail-heading"><span>{storeName(item.store_id)}</span><span className={`loop-status ${item.case_status.toLowerCase().replaceAll(' ', '-')}`}>{item.case_status}</span></div>
    <h2 id="case-title">{item.customer.name}</h2>
    <div className="loop-person"><Star size={16} />{item.rating} / 5<span>{item.customer.is_sparks_customer ? 'Sparks Customer' : 'Non-Sparks Customer'}</span></div>
    <blockquote>{item.feedback}</blockquote>
    <dl className="loop-ownership">
      <div><dt>Email</dt><dd>{item.customer.email ?? 'Not provided'}</dd></div>
      <div><dt>Phone</dt><dd>{item.customer.phone_number ?? 'Not provided'}</dd></div>
      <div><dt>Sparks ID</dt><dd>{item.customer.sparks_id ?? 'Not provided'}</dd></div>
      <div><dt>Received</dt><dd>{new Date(item.created_at).toLocaleString()}</dd></div>
      <div><dt>Customer notification</dt><dd>{item.customer_communication.status}</dd></div>
    </dl>
    <section className="case-support" aria-label="Model decision support">
      <div><h3>Sentiment</h3><span className={`sentiment ${item.sentiment.label.toLowerCase()}`}>{item.sentiment.label}</span><p>Sentiment model support: {percent(item.sentiment.confidence)}</p></div>
      <div><h3>Genuine feedback</h3><strong>{assessment.model_label}</strong><p>Model confidence: {percent(assessment.model_confidence)}</p></div>
      <div><h3>Model recommendation</h3><strong>{assessment.model_recommendation}</strong><small>Colleague confirmation required</small></div>
      <div><h3>Incentive recommendation</h3><p>{assessment.incentive_tier === 'high' ? 'High tier' : assessment.incentive_tier === 'tier_based' ? 'Standard reward' : 'None'} / Not issued</p></div>
      <details><summary>Assessment details</summary><p>{assessment.model_reason}</p><p>{assessment.reason_code} / Review threshold: {percent(assessment.threshold)}</p>
        <p>{item.sentiment.model_name} / {item.sentiment.model_version}</p><p>{item.sentiment.confidence_kind}</p><p>{assessment.model_name} / {assessment.model_version}</p>
      </details>
    </section>
    <div className="case-decision"><strong>Colleague decision: {assessment.final_decision ?? 'Awaiting Colleague Review'}</strong>
      {assessment.decision_reason && <p>{assessment.decision_reason}</p>}
      {assessment.confirmed_at && <small>{assessment.confirmed_by} / {new Date(assessment.confirmed_at).toLocaleString()}</small>}
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    <section className="loop-message" aria-label="Customer Communication">
      <h3>Customer Communication <span>POC simulation</span></h3>
      <label htmlFor="communication-template">Communication template</label>
      <select id="communication-template" value={template} disabled={busy} onChange={event => setTemplate(event.target.value as Template)}>
        <option value="general">General resolution</option><option value="reward_eligible" disabled={assessment.final_decision !== 'Reward Eligible'}>Reward eligible</option>
        <option value="not_eligible" disabled={assessment.final_decision !== 'Not Eligible'}>Not eligible</option>
      </select>
      <p aria-label="Message preview">{item.communication_templates[template]}</p>
      <button className="primary-button" type="button" disabled={busy} onClick={() => void mutate('notify', { template })}><Mail size={17} />Send customer update</button>
      {item.customer_communication.sent_at && <p>Recorded {new Date(item.customer_communication.sent_at).toLocaleString()} / {item.customer_communication.channel}</p>}
    </section>
    <form className="loop-resolution" aria-label="Resolution actions" onSubmit={confirm}>
      <h3>Resolution actions</h3>
      <fieldset disabled={busy}>
        <label htmlFor="case-store">Assigned store</label><select id="case-store" value={store} onChange={event => setStore(event.target.value)}>{stores.map(entry => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select>
        <label htmlFor="case-status">Update case status</label><select id="case-status" value={status} onChange={event => setStatus(event.target.value as CaseStatus)}>{statuses.map(entry => <option key={entry} disabled={(item.case_status === 'Resolved' && entry !== 'Resolved') || (item.case_status === 'In Progress' && entry === 'Opened')}>{entry}</option>)}</select>
        <label htmlFor="case-colleague">Colleague name</label><input id="case-colleague" value={colleague} required maxLength={120} onChange={event => setColleague(event.target.value)} />
        <label htmlFor="decision-reason">Decision reason</label><textarea id="decision-reason" required maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} />
        <label htmlFor="colleague-note">Internal note (optional)</label><textarea id="colleague-note" maxLength={2000} value={note} onChange={event => setNote(event.target.value)} />
        <div className="decision-actions">
          <button className="primary-button" type="submit" value="Reward Eligible"><Check size={16} />Confirm Reward Eligible</button>
          <button className="secondary-button" type="submit" value="Not Eligible"><CircleMinus size={16} />Confirm Not Eligible</button>
          <button className="secondary-button" type="submit" value="Awaiting Colleague Review" disabled={status === 'Resolved'}><Clock3 size={16} />Keep Awaiting Review</button>
        </div>
      </fieldset>
    </form>
    <section className="loop-timeline" aria-label="Action history"><h3>Action history</h3><ol>{item.activity_history.map((event, index) => <li key={index}><span className="loop-event-dot" /><div><span>{new Date(event.timestamp).toLocaleString()}</span><p>{event.action}</p>{event.note && <p>{event.note}</p>}{event.colleague && <p>{event.colleague}</p>}{event.template && <p>{event.template} / {event.channel}</p>}</div></li>)}</ol></section>
  </section>
}

export default function FeedbackResolutionHub({ revision = 0, requestedCaseId = '', compact = false, onChanged = () => {} }: {
  revision?: number; requestedCaseId?: string; compact?: boolean; onChanged?: () => void
}) {
  const [store, setStore] = useState('')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [decision, setDecision] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<CasePage | null>(null)
  const [insights, setInsights] = useState<Insights | null>(null)
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [loadedKey, setLoadedKey] = useState('')
  const [opening, setOpening] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reload, setReload] = useState(0)
  const loadKey = JSON.stringify([store, status, debouncedSearch, decision, page, revision, reload])
  const loading = loadedKey !== loadKey
  const detailSequence = useRef(0)
  const openRequestedCase = useEffectEvent((identity: string, signal: AbortSignal) => { void openCase(identity, signal) })
  useEffect(() => { const timer = setTimeout(() => setDebouncedSearch(search), 250); return () => clearTimeout(timer) }, [search])
  useEffect(() => {
    const controller = new AbortController()
    const query = new URLSearchParams({ page: String(page), page_size: '10' })
    if (store) query.set('store_id', store)
    if (status) query.set('status', status)
    if (decision) query.set('decision', decision)
    if (debouncedSearch) query.set('search', debouncedSearch)
    void Promise.all([
      caseApi<CasePage>(`colleague/feedback-cases?${query}`, { signal: controller.signal }),
      caseApi<Insights>(`colleague/insights${store ? `?store_id=${encodeURIComponent(store)}` : ''}`, { signal: controller.signal }),
    ]).then(([cases, summary]) => { if (!controller.signal.aborted) { setData(cases); setInsights(summary); setError('') } })
      .catch(caught => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Cases unavailable. Please retry.') })
      .finally(() => { if (!controller.signal.aborted) setLoadedKey(loadKey) })
    return () => controller.abort()
  }, [store, status, debouncedSearch, decision, page, revision, reload, loadKey])
  useEffect(() => {
    const controller = new AbortController()
    if (requestedCaseId) openRequestedCase(requestedCaseId, controller.signal)
    return () => controller.abort()
  }, [requestedCaseId])

  async function openCase(identity: string, signal?: AbortSignal) {
    const request = ++detailSequence.current
    setOpening(true); setError(''); setNotice('')
    try {
      const item = await caseApi<CaseDetail>(`colleague/feedback-cases/${identity}`, { signal })
      if (request !== detailSequence.current || signal?.aborted) return
      setDetail(item)
      if (!item.notification.is_read) {
        await caseApi(`colleague/notifications/${identity}/read`, { method: 'PATCH' })
        onChanged()
      }
    } catch (caught) { if (request === detailSequence.current && !signal?.aborted) setError(caught instanceof Error ? caught.message : 'Case unavailable. Please retry.') }
    finally { if (request === detailSequence.current && !signal?.aborted) setOpening(false) }
  }

  function clearSelection() { setPage(1); setDetail(null); detailSequence.current++; setOpening(false) }

  return <div className="closed-loop">
    <div className="page-heading"><div><p className="eyebrow">M&S / STORE COLLEAGUE</p><h1>{compact ? 'Store Colleague Perspective' : 'Feedback Resolution Hub'}</h1></div></div>
    <div className="loop-toolbar">
      <div><label htmlFor="loop-store">Choose Store</label><select id="loop-store" value={store} onChange={event => { setStore(event.target.value); clearSelection() }}><option value="">All stores</option>{stores.map(entry => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></div>
      <div><label htmlFor="loop-status">Case Status</label><select id="loop-status" value={status} onChange={event => { setStatus(event.target.value); clearSelection() }}><option value="">All statuses</option>{statuses.map(entry => <option key={entry}>{entry}</option>)}</select></div>
      <div className="loop-search"><label htmlFor="loop-search">Search Cases</label><span><Search size={17} /><input id="loop-search" type="search" maxLength={200} value={search} onChange={event => { setSearch(event.target.value); clearSelection() }} placeholder="Case reference or feedback" /></span></div>
      <div><label htmlFor="loop-decision">Reward decision</label><select id="loop-decision" value={decision} onChange={event => { setDecision(event.target.value); clearSelection() }}><option value="">All decisions</option>{decisions.map(entry => <option key={entry}>{entry}</option>)}</select></div>
    </div>
    <ColleagueInsights insights={insights} />
    <p className="loop-notice" role="status">{notice}</p>
    {error && <div className="error" role="alert"><span>{error}</span><button className="secondary-button" onClick={() => setReload(value => value + 1)}>Retry</button></div>}
    <div className="loop-workspace">
      <aside className="loop-case-list" aria-label="Feedback cases" aria-busy={loading}>
        <div className="loop-list-heading"><h2>Received feedback</h2><span>{data?.total ?? 0} cases</span></div>
        {loading && <p><LoaderCircle className="spin" size={16} aria-label="Loading cases" /></p>}
        {data?.items.map(item => <button key={item.case_id} className={`loop-case ${detail?.case_id === item.case_id ? 'selected' : ''}`} aria-pressed={detail?.case_id === item.case_id} onClick={() => void openCase(item.case_id)}>
          <span className="loop-case-meta"><span>{reference(item.case_id)}</span><span className={`loop-status ${item.case_status.toLowerCase().replaceAll(' ', '-')}`}>{item.case_status}</span></span>
          <strong>{item.feedback.length > 110 ? item.feedback.slice(0, 110) + '...' : item.feedback}</strong>
          <span className="loop-case-store"><Store size={13} />{storeName(item.store_id)}</span>
          <span className="loop-case-category">{item.rating} / 5 stars / {item.sentiment.label}</span>
          <span className="loop-case-category">{item.reward_assessment.final_decision ?? 'Awaiting Colleague Review'}</span>
          {!item.notification.is_read && <span className="case-unread">New</span>}
        </button>)}
        {!loading && data?.total === 0 && <p className="live-case-summary">No matching cases.</p>}
        <div className="case-pagination"><button className="icon-button" aria-label="Previous cases" title="Previous cases" disabled={page === 1 || loading} onClick={() => setPage(value => value - 1)}><ArrowLeft size={17} /></button><span>Page {page}</span><button className="icon-button" aria-label="Next cases" title="Next cases" disabled={!data || page * data.page_size >= data.total || loading} onClick={() => setPage(value => value + 1)}><ArrowRight size={17} /></button></div>
      </aside>
      {opening ? <div className="loop-empty"><LoaderCircle className="spin" size={24} aria-label="Loading case" /></div> : detail ? <FeedbackCaseDetail key={`${detail.case_id}-${reload}`} item={detail} onSaved={updated => { setDetail(updated); onChanged() }} onReload={() => { setReload(value => value + 1); void openCase(detail.case_id) }} onNotice={setNotice} /> : <section className="loop-empty"><Search size={25} /><h2>No case selected</h2></section>}
    </div>
  </div>
}