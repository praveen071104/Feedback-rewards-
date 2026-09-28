import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Mail, RefreshCw, Save } from 'lucide-react'

type Fields = {
  status: 'open' | 'in_progress' | 'resolved'
  assignee: string
  customerEmail: string
  contactConsent: boolean
  contactStatus: 'not_contacted' | 'contact_recorded'
  actionTaken: string
  customerUpdate: string
}
type Workflow = Fields & {
  ticketId: string
  version: number
  updatedAt: string | null
  history: (Fields & { recordedAt: string })[]
}
const statuses = { open: 'Opened', in_progress: 'In Progress', resolved: 'Resolved' }

function isWorkflow(value: unknown): value is Workflow {
  if (!value || typeof value !== 'object') return false
  const data = value as Record<string, unknown>
  return typeof data.ticketId === 'string' && Number.isInteger(data.version) && Number(data.version) >= 0 &&
    Object.hasOwn(statuses, String(data.status)) &&
    ['assignee', 'customerEmail', 'actionTaken', 'customerUpdate'].every(key => typeof data[key] === 'string') &&
    typeof data.contactConsent === 'boolean' && ['not_contacted', 'contact_recorded'].includes(String(data.contactStatus)) &&
    Array.isArray(data.history) && data.history.every(entry => entry && typeof entry.recordedAt === 'string' &&
      typeof entry.assignee === 'string' && typeof entry.actionTaken === 'string' && typeof entry.customerUpdate === 'string' && Object.hasOwn(statuses, entry.status))
}

export default function TicketWorkflow({ ticketId, busy }: { ticketId: string; busy: boolean }) {
  const [saved, setSaved] = useState<Workflow | null>(null)
  const [draft, setDraft] = useState<Fields | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [reload, setReload] = useState(0)
  const operation = useRef<string | null>(null)
  const inFlight = useRef(false)
  useEffect(() => {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000)
    let active = true
    fetch(`/api/tickets/${ticketId}/workflow`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Store actions could not be loaded. Retry when ticket storage is available.')
      const data: unknown = await response.json()
      if (!isWorkflow(data) || data.ticketId !== ticketId) throw new Error('Invalid store action response.')
      if (active) {
        setSaved(data)
        setDraft(data)
        operation.current = null
      }
    }).catch(caught => {
      if (active) setError(caught instanceof Error ? caught.message : 'Unable to load store actions.')
    }).finally(() => { clearTimeout(timeout); if (active) setLoading(false) })
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [ticketId, reload])

  function change(update: Partial<Fields>) {
    setDraft(current => current ? { ...current, ...update } : current)
    operation.current = null
    setMessage('')
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!draft || !saved || inFlight.current || busy) return
    inFlight.current = true
    setSaving(true)
    setError('')
    setMessage('')
    operation.current ??= crypto.randomUUID()
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000)
    try {
      const fields: Fields = { status: draft.status, assignee: draft.assignee, customerEmail: draft.customerEmail,
        contactConsent: draft.contactConsent, contactStatus: draft.contactStatus,
        actionTaken: draft.actionTaken, customerUpdate: draft.customerUpdate }
      const response = await fetch(`/api/tickets/${ticketId}/workflow`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...fields, operationId: operation.current, expectedVersion: saved.version }), signal: controller.signal,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the assignment, completed action and customer contact details before saving.')
      if (!isWorkflow(data) || data.ticketId !== ticketId) throw new Error('Saving was not confirmed. Retry this update.')
      setSaved(data)
      setDraft(data)
      operation.current = null
      setMessage('Store actions saved. No message sent by this app.')
    } catch (caught) {
      setError(caught instanceof Error && caught.name !== 'AbortError' ? caught.message : 'Saving was not confirmed. Retry this update.')
    } finally {
      clearTimeout(timeout)
      inFlight.current = false
      setSaving(false)
    }
  }

  const locked = busy || saving || loading
  return <section className="store-workflow" aria-label="Store follow-up">
    <div className="workflow-heading"><h3>Store follow-up</h3>
      <button type="button" className="icon-button" title="Reload store actions" aria-label="Reload store actions" disabled={locked}
        onClick={() => { if (window.confirm('Reload saved actions and discard unsaved changes?')) { setLoading(true); setError(''); setMessage(''); setReload(current => current + 1) } }}><RefreshCw size={16} /></button>
    </div>
    {loading && <p>Loading store actions...</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {saved && <p className="workflow-summary">{statuses[saved.status]} · {saved.assignee || 'Unassigned'} · {saved.contactStatus === 'contact_recorded' ? 'Contact recorded by colleague' : 'Customer not contacted'}</p>}
    {draft && saved && <form onSubmit={save} aria-label="Store action form">
      <fieldset disabled={locked}>
        <label htmlFor="ticket-assignee">Assigned colleague</label>
        <input id="ticket-assignee" value={draft.assignee} maxLength={120} required={draft.status !== 'open'} onChange={event => change({ assignee: event.target.value })} />
        <label htmlFor="ticket-status">Work status</label>
        <select id="ticket-status" value={draft.status} onChange={event => change({ status: event.target.value as Fields['status'] })}>
          <option value="open" disabled={saved.status === 'resolved'}>Opened</option><option value="in_progress" disabled={saved.status === 'resolved'}>In Progress</option><option value="resolved">Resolved</option>
        </select>
        <label htmlFor="ticket-action">Action taken</label>
        <textarea id="ticket-action" value={draft.actionTaken} maxLength={2000} required={draft.status === 'resolved'} onChange={event => change({ actionTaken: event.target.value })} />
        <label htmlFor="ticket-update">Customer Communication</label>
        <textarea id="ticket-update" value={draft.customerUpdate} maxLength={2000} required={draft.status === 'resolved' || draft.contactStatus === 'contact_recorded'} onChange={event => change({ customerUpdate: event.target.value })} />
        <label htmlFor="ticket-email">Customer email (optional)</label>
        <input id="ticket-email" type="email" value={draft.customerEmail} maxLength={254} onChange={event => change({ customerEmail: event.target.value, contactStatus: 'not_contacted' })} />
        <label className="workflow-checkbox"><input type="checkbox" checked={draft.contactConsent} onChange={event => change({ contactConsent: event.target.checked, contactStatus: 'not_contacted' })} />Customer permits storage and follow-up contact</label>
        <label htmlFor="ticket-contact">Contact record</label>
        <select id="ticket-contact" value={draft.contactStatus} onChange={event => change({ contactStatus: event.target.value as Fields['contactStatus'] })}>
          <option value="not_contacted">Not contacted</option><option value="contact_recorded">Contact completed outside this app</option>
        </select>
        <button className="primary-button" type="submit"><Save size={17} />{saving ? 'Saving actions...' : 'Save store actions'}</button>
      </fieldset>
    </form>}
    {saved?.customerEmail && saved.contactConsent && saved.assignee && saved.customerUpdate &&
      <a className="workflow-email" href={`mailto:${encodeURIComponent(saved.customerEmail)}?subject=${encodeURIComponent('Your store feedback')}&body=${encodeURIComponent(saved.customerUpdate + '\n\n' + saved.assignee)}`}><Mail size={17} />Open email draft</a>}
    {message && <p role="status">{message}</p>}
    {!!saved?.history.length && <details><summary>Saved action history ({saved.history.length})</summary>
      <ol>{saved.history.map((entry, index) => <li key={index}>
        <strong>{statuses[entry.status]} · {entry.assignee || 'Unassigned'}</strong>
        <time dateTime={entry.recordedAt}>{new Date(entry.recordedAt).toLocaleString()}</time>
        <p>{entry.actionTaken}</p><p>{entry.customerUpdate}</p>
        <small>{entry.contactStatus === 'contact_recorded' ? 'Contact recorded by colleague' : 'No contact recorded'}</small>
      </li>)}</ol>
    </details>}
  </section>
}