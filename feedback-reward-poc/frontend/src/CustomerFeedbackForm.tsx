import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, Check, LoaderCircle, Star } from 'lucide-react'
import { caseApi, stores } from './caseApi'
import './CustomerJourney.css'

const ratingDescriptions = ['Very Poor', 'Poor', 'Satisfactory', 'Good', 'Very Good']
const emptyForm = { name: '', email: '', phone_number: '', sparks_id: '', feedback: '', rating: 0 }

export function StarRating({ value, onChange, disabled }: { value: number; onChange: (value: number) => void; disabled: boolean }) {
  return <fieldset className="star-rating" disabled={disabled}>
    <legend>Rating</legend>
    <div className="stars">{ratingDescriptions.map((description, index) => <label key={description} title={`${index + 1}: ${description}`}>
      <input type="radio" name="rating" value={index + 1} checked={value === index + 1} required onChange={() => onChange(index + 1)} aria-label={`${index + 1} ${index === 0 ? 'star' : 'stars'}: ${description}`} />
      <Star size={25} aria-hidden="true" fill={value > index ? 'currentColor' : 'none'} />
    </label>)}</div>
    <small aria-live="polite">{value ? ratingDescriptions[value - 1] : 'Not rated'}</small>
  </fieldset>
}

export function SubmissionSuccess({ caseId }: { caseId: string }) {
  return <div className="submission-success" role="status"><Check size={25} /><div>
    <strong>Feedback submitted successfully.</strong><small>Case reference: {caseId}</small>
  </div></div>
}

export default function CustomerFeedbackForm({ onSubmitted }: { onSubmitted: () => void }) {
  const initialStore = new URLSearchParams(window.location.search).get('store')
  const [store, setStore] = useState(stores.some(item => item.id === initialStore) ? initialStore! : 'unspecified')
  const [form, setForm] = useState(emptyForm)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const inFlight = useRef(false)
  const submission = useRef<string | null>(null)
  function change(patch: Partial<typeof emptyForm>) {
    setForm(current => ({ ...current, ...patch })); setError(''); setSuccess(''); submission.current = null
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (inFlight.current) return
    if (!form.email.trim() && !form.phone_number.trim()) { setError('Enter an email address or phone number.'); return }
    if (!form.name.trim() || !/\p{L}/u.test(form.feedback) || !form.rating) {
      setError('Complete all required fields and select a rating.'); return
    }
    if (form.phone_number.trim() && (!/^\+?[0-9 ()-]+$/.test(form.phone_number.trim()) || !/^\d{7,15}$/.test(form.phone_number.replace(/\D/g, '')))) {
      setError('Enter a phone number with 7 to 15 digits.'); return
    }
    inFlight.current = true; setBusy(true); setError(''); setSuccess('')
    submission.current ??= crypto.randomUUID()
    try {
      const result = await caseApi<{ case_id: string; status: string }>('customer-feedback', { method: 'POST', body: JSON.stringify({
        ...form, email: form.email.trim() || null, phone_number: form.phone_number.trim() || null,
        is_sparks_customer: Boolean(form.sparks_id.trim()), sparks_id: form.sparks_id.trim() || null,
        submission_id: submission.current, store_id: store,
      }) })
      if (result.status !== 'submitted' || typeof result.case_id !== 'string') throw new Error('Submission was not confirmed. Please retry.')
      setSuccess(result.case_id); setForm(emptyForm); submission.current = null; onSubmitted()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Submission failed. Please retry.') }
    finally { inFlight.current = false; setBusy(false) }
  }
  return <section className="customer-journey" aria-labelledby="customer-title">
    <div className="page-heading"><div><p className="eyebrow">M&S / CUSTOMER FEEDBACK</p><h1 id="customer-title">Tell us about your visit</h1></div></div>
    {success && <SubmissionSuccess caseId={success} />}
    <form onSubmit={submit} className="customer-form">
      <fieldset disabled={busy}>
        <label htmlFor="customer-store">Store</label><select id="customer-store" value={store} onChange={event => { setStore(event.target.value); submission.current = null; setSuccess('') }}>
          {stores.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <label htmlFor="customer-name">Customer Name <span>(required)</span></label>
        <input id="customer-name" autoComplete="name" value={form.name} required maxLength={120} onChange={event => change({ name: event.target.value })} />
        <fieldset className="contact-fields"><legend>Contact Method <span>(email or phone required)</span></legend>
          <div><label htmlFor="customer-email">Email address</label><input id="customer-email" type="email" autoComplete="email" maxLength={254} value={form.email} onChange={event => change({ email: event.target.value })} /></div>
          <div><label htmlFor="customer-phone">Phone number</label><input id="customer-phone" type="tel" autoComplete="tel" maxLength={30} value={form.phone_number} onChange={event => change({ phone_number: event.target.value })} /></div>
        </fieldset>
        <label htmlFor="sparks-id">Sparks ID <span>(optional)</span></label>
        <input id="sparks-id" value={form.sparks_id} maxLength={64} onChange={event => change({ sparks_id: event.target.value })} />
        <label htmlFor="customer-feedback">Feedback <span>(required)</span></label><textarea id="customer-feedback" maxLength={5000} required value={form.feedback} aria-describedby="customer-counter" onChange={event => change({ feedback: event.target.value })} />
        <small id="customer-counter" className="customer-counter">{form.feedback.length.toLocaleString()} / 5,000</small>
        <StarRating value={form.rating} onChange={rating => change({ rating })} disabled={busy} />
        <p className="privacy-notice">Your information will be used to review your feedback and provide related updates.</p>
        <button className="primary-button" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}{busy ? 'Submitting feedback...' : 'Submit Feedback'}</button>
      </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  </section>
}