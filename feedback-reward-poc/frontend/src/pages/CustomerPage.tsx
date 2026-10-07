import * as React from 'react'
import { CheckCircle2, Loader2, Send } from 'lucide-react'
import { api, DEFAULT_STORES, type FeedbackResult, type Store } from '../lib/api'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input, Label, Select, Textarea } from '../components/ui/input'
import { StarRating } from '../components/StarRating'
import { fmtSparks, SPARKS_LENGTH } from '../lib/format'

const EMPTY = {
  name: '',
  email: '',
  phone: '',
  store_id: 'unspecified',
  stars: 0,
  feedback: '',
  sparks_member: false,
  sparks_id: '',
}

export default function CustomerPage() {
  const [stores, setStores] = React.useState<Store[]>(DEFAULT_STORES)
  const [form, setForm] = React.useState(EMPTY)
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [result, setResult] = React.useState<FeedbackResult | null>(null)

  React.useEffect(() => {
    api.stores().then(setStores)
  }, [])

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (form.stars === 0) {
      setError('Please choose a star rating.')
      return
    }
    if (form.sparks_member && form.sparks_id.replace(/\D/g, '').length !== SPARKS_LENGTH) {
      setError('Your Sparks card number must be exactly 16 digits.')
      return
    }
    setSubmitting(true)
    try {
      const r = await api.submitFeedback({
        name: form.name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || undefined,
        store_id: form.store_id,
        stars: form.stars,
        feedback: form.feedback.trim(),
        sparks_member: form.sparks_member,
        sparks_id: form.sparks_member ? form.sparks_id.replace(/\D/g, '') : null,
      })
      setResult(r)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  if (result) {
    return (
      <ThankYou
        result={result}
        onAddDetail={() => setResult(null)}
        onAnother={() => { setResult(null); setForm(EMPTY) }}
      />
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="space-y-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-display">Tell us about your experience</h1>
          <p className="text-mns-mute mt-2">
            Your feedback helps us improve M&amp;S products and service.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Submit Feedback</CardTitle>
            <CardDescription>Fields marked * are required.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-5">
              <div>
                <Label htmlFor="store">Store</Label>
                <Select
                  id="store"
                  value={form.store_id}
                  onChange={(e) => set('store_id', e.target.value)}
                  className="mt-1.5"
                >
                  {stores.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <Label>Overall rating *</Label>
                <div className="mt-1.5">
                  <StarRating value={form.stars} onChange={(v) => set('stars', v)} disabled={submitting} />
                </div>
              </div>

              <div>
                <Label htmlFor="feedback">Feedback *</Label>
                <Textarea
                  id="feedback"
                  required
                  minLength={1}
                  maxLength={5000}
                  rows={5}
                  placeholder="Tell us about your visit."
                  value={form.feedback}
                  onChange={(e) => set('feedback', e.target.value)}
                  className="mt-1.5"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="name">Your name *</Label>
                  <Input
                    id="name"
                    required
                    maxLength={120}
                    value={form.name}
                    onChange={(e) => set('name', e.target.value)}
                    className="mt-1.5"
                  />
                </div>
                <div>
                  <Label htmlFor="email">Email *</Label>
                  <Input
                    id="email"
                    type="email"
                    required
                    value={form.email}
                    onChange={(e) => set('email', e.target.value)}
                    placeholder="name@example.com"
                    className="mt-1.5"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="phone">Phone (optional)</Label>
                <Input
                  id="phone"
                  type="tel"
                  value={form.phone}
                  onChange={(e) => set('phone', e.target.value)}
                  className="mt-1.5"
                />
              </div>

              <div className="rounded-lg border border-mns-line bg-mns-cream/40 p-4 space-y-3">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.sparks_member}
                    onChange={(e) => set('sparks_member', e.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-mns-navy/30 text-mns-gold focus:ring-mns-gold"
                  />
                  <span className="text-sm">
                    <span className="font-medium text-mns-navy">Sparks member</span>
                  </span>
                </label>
                {form.sparks_member && (
                  <div>
                    <Label htmlFor="sparks_id">Sparks card number *</Label>
                    <Input
                      id="sparks_id"
                      required
                      inputMode="numeric"
                      autoComplete="off"
                      maxLength={19}
                      value={form.sparks_id}
                      onChange={(e) => set('sparks_id', fmtSparks(e.target.value.slice(0, 19)))}
                      placeholder="1234 5678 9012 3456"
                      className="mt-1.5 font-mono tracking-wider"
                    />
                  </div>
                )}
              </div>

              {error && (
                <div className="rounded-md bg-mns-danger/10 text-mns-danger text-sm px-3 py-2">{error}</div>
              )}

              <Button type="submit" variant="gold" size="lg" disabled={submitting} className="w-full">
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Sending…
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" /> Submit feedback
                  </>
                )}
              </Button>
              <p className="text-xs text-mns-mute">
                We may contact you about your feedback.
              </p>
            </form>
          </CardContent>
        </Card>
      </div>

    </div>
  )
}

function ThankYou({ result, onAnother, onAddDetail }: { result: FeedbackResult; onAnother: () => void; onAddDetail: () => void }) {
  return (
    <div className="max-w-2xl mx-auto">
      <Card>
        <CardHeader>
          <CheckCircle2 className="mb-2 h-6 w-6 text-mns-success" />
          <CardTitle>Thank you for your feedback</CardTitle>
          <CardDescription>Reference: {result.submission_id}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div>
              <div className="mns-section-label mb-1">Acknowledgement (simulated)</div>
              <p className="text-base leading-relaxed whitespace-pre-line">{result.customer_reply}</p>
            </div>
            {result.reward_followup && (
              <div className="border-t border-mns-line pt-3">
                <div className="mns-section-label mb-1">Reward eligibility follow-up (simulated)</div>
                <p className="text-sm leading-relaxed whitespace-pre-line">{result.reward_followup}</p>
              </div>
            )}
          </div>
          {result.needs_more_detail && (
            <div className="mt-6 rounded-lg border border-mns-gold/40 bg-mns-cream p-4">
              <div className="font-medium text-mns-navy">More detail</div>
              <p className="mt-0.5 text-xs text-mns-mute">
                Add what happened, where and when to help us review.
              </p>
              <Button variant="gold" size="sm" className="mt-3" onClick={onAddDetail}>
                Add details
              </Button>
            </div>
          )}
          <Button variant="outline" className="mt-6" onClick={onAnother}>
            Submit another
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
