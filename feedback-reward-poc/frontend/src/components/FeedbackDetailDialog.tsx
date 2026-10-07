import * as React from 'react'
import { Loader2, Mail, MapPin, Phone, Sparkles, Star, Ticket as TicketIcon, User } from 'lucide-react'
import { api, type FeedbackDetail } from '../lib/api'
import { Dialog, DialogBody, DialogContent, DialogHeader, DialogTitle } from './ui/dialog'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Select, Textarea } from './ui/input'
import { PipelineTrace } from './PipelineTrace'
import { fmtGBP, fmtSparks } from '../lib/format'

export function FeedbackDetailDialog({
  submissionId,
  open,
  onOpenChange,
}: {
  submissionId: string | null
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const [data, setData] = React.useState<FeedbackDetail | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [tier, setTier] = React.useState<'none' | 'low' | 'mid' | 'high'>('none')
  const [eligibilityNote, setEligibilityNote] = React.useState('')
  const [savingEligibility, setSavingEligibility] = React.useState(false)
  const [revision, setRevision] = React.useState(0)

  React.useEffect(() => {
    if (!open || !submissionId) {
      setData(null)
      setError(null)
      return
    }
    api
      .getFeedbackDetail(submissionId)
      .then((d) => {
        setData(d)
        setTier(d.reward_eligibility.tier ?? d.reward_eligibility.suggested_tier)
        setEligibilityNote(d.reward_eligibility.note ?? '')
        setError(null)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
  }, [open, submissionId, revision])

  async function saveEligibility() {
    if (!submissionId) return
    setSavingEligibility(true)
    setError(null)
    try {
      await api.decideRewardEligibility(submissionId, tier, eligibilityNote || undefined)
      setRevision((value) => value + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to save eligibility decision.')
    } finally {
      setSavingEligibility(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Feedback details</DialogTitle>
          {submissionId && (
            <p className="text-xs text-mns-mute mt-1 font-mono">{submissionId}</p>
          )}
        </DialogHeader>

        {error ? (
          <DialogBody>
            <p className="text-mns-danger text-sm">{error}</p>
          </DialogBody>
        ) : !data ? (
          <DialogBody>
            <div className="flex items-center gap-2 text-mns-mute py-10 justify-center">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading…
            </div>
          </DialogBody>
        ) : (
          <DialogBody>
            <HeaderBadges data={data} />
            <blockquote className="text-base italic border-l-4 border-mns-gold/60 pl-3 py-2 bg-mns-cream/60 rounded-r">
              {data.text}
            </blockquote>
            <CustomerBlock data={data} />
            <EligibilityBlock
              data={data}
              tier={tier}
              onTierChange={setTier}
              note={eligibilityNote}
              onNoteChange={setEligibilityNote}
              onSave={saveEligibility}
              saving={savingEligibility}
            />
            <AnalysisBlock data={data} />
            {data.ticket && <TicketBlock ticket={data.ticket} />}
            {data.reward && <RewardBlock reward={data.reward} />}
          </DialogBody>
        )}
      </DialogContent>
    </Dialog>
  )
}

function EligibilityBlock({
  data, tier, onTierChange, note, onNoteChange, onSave, saving,
}: {
  data: FeedbackDetail
  tier: 'none' | 'low' | 'mid' | 'high'
  onTierChange: (tier: 'none' | 'low' | 'mid' | 'high') => void
  note: string
  onNoteChange: (note: string) => void
  onSave: () => void
  saving: boolean
}) {
  const review = data.reward_eligibility
  const decided = review.eligible !== null
  return (
    <Section label="Reward eligibility review">
      <div className="space-y-3 rounded-md border border-mns-line p-3">
        <p className="text-sm text-mns-mute">
          Backend suggestion: {review.suggested_tier === 'none' ? 'not eligible' : `${review.suggested_tier} tier · ${fmtGBP(review.suggested_amount_gbp)}`}
        </p>
        {decided ? (
          <div className="space-y-1 text-sm">
            <p className="font-medium text-mns-navy">
              Colleague decision: {review.eligible ? `${review.tier} tier · ${fmtGBP(data.reward?.amount_gbp ?? 0)}` : 'Not eligible'}
            </p>
            {review.decided_by && <p className="text-xs text-mns-mute">Reviewed by {review.decided_by}{review.decided_at ? ` · ${new Date(review.decided_at).toLocaleString()}` : ''}</p>}
            {review.note && <p className="text-sm">{review.note}</p>}
            {review.eligible && <p className="text-xs text-mns-mute">Added to the Rewards queue; the eligibility follow-up is recorded as simulated.</p>}
          </div>
        ) : (
          <>
            <label className="block space-y-1 text-sm">
              <span>Eligibility decision and incentive tier</span>
              <Select value={tier} onChange={(event) => onTierChange(event.target.value as typeof tier)}>
                <option value="none">Not eligible</option>
                <option value="low">Eligible · Low · £2.00</option>
                <option value="mid">Eligible · Mid · £3.50</option>
                <option value="high">Eligible · High · £5.00</option>
              </Select>
            </label>
            <Textarea
              rows={2}
              maxLength={500}
              value={note}
              onChange={(event) => onNoteChange(event.target.value)}
              placeholder="Optional eligibility note"
            />
            <Button variant="gold" size="sm" disabled={saving} onClick={onSave}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Confirm eligibility decision
            </Button>
          </>
        )}
      </div>
    </Section>
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <h4 className="mns-section-label mb-2">{label}</h4>
      {children}
    </section>
  )
}

function HeaderBadges({ data }: { data: FeedbackDetail }) {
  const a = data.analysis
  return (
    <div className="flex flex-wrap items-center gap-2">
      {a.category && <Badge variant={catVariant(a.category)}>{a.category.replace('_', ' ')}</Badge>}
      {typeof a.category_confidence === 'number' && (
        <Badge variant={a.category_confidence >= 0.7 ? 'success' : a.category_confidence >= 0.55 ? 'warn' : 'danger'}>
          {Math.round(a.category_confidence * 100)}% confident
        </Badge>
      )}
      {a.needs_review && <Badge variant="warn">needs review</Badge>}
      {a.priority && a.priority !== 'low' && (
        <Badge variant={a.priority === 'high' ? 'danger' : 'warn'}>priority: {a.priority}</Badge>
      )}
      {a.overall_sentiment && (
        <Badge variant={sentVariant(a.overall_sentiment)}>sentiment: {a.overall_sentiment}</Badge>
      )}
      {a.reward_tier && a.reward_tier !== 'none' && (
        <Badge variant="gold" className="flex items-center gap-1">
          <Sparkles className="w-3 h-3" /> {a.reward_tier} tier
        </Badge>
      )}
      {data.ticket && (
        <Badge variant="warn" className="flex items-center gap-1">
          <TicketIcon className="w-3 h-3" /> ticket #{data.ticket.id}
        </Badge>
      )}
      {data.stars !== null && (
        <Badge variant="default" className="flex items-center gap-1">
          <Star className="w-3 h-3 fill-mns-gold text-mns-gold" /> {data.stars}/5
        </Badge>
      )}
      <span className="ml-auto text-xs text-mns-mute">
        {new Date(data.created_at).toLocaleString()}
      </span>
    </div>
  )
}

function CustomerBlock({ data }: { data: FeedbackDetail }) {
  const c = data.customer
  return (
    <Section label="Customer">
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-y-1.5 gap-x-6 text-sm">
        {c.name && (
          <li className="flex items-center gap-2">
            <User className="w-3.5 h-3.5 text-mns-mute" /> {c.name}
          </li>
        )}
        {c.email && (
          <li className="flex items-center gap-2">
            <Mail className="w-3.5 h-3.5 text-mns-mute" /> {c.email}
          </li>
        )}
        {c.phone && (
          <li className="flex items-center gap-2">
            <Phone className="w-3.5 h-3.5 text-mns-mute" /> {c.phone}
          </li>
        )}
        {data.store_id && (
          <li className="flex items-center gap-2">
            <MapPin className="w-3.5 h-3.5 text-mns-mute" /> {data.store_id}
          </li>
        )}
        {c.sparks_member && (
          <li className="flex items-center gap-2 text-mns-navy font-medium">
            <Sparkles className="w-3.5 h-3.5 text-mns-gold" />
            Sparks member{c.sparks_id ? ` · ${fmtSparks(c.sparks_id)}` : ''}
          </li>
        )}
      </ul>
    </Section>
  )
}

function AnalysisBlock({ data }: { data: FeedbackDetail }) {
  const a = data.analysis
  return (
    <>
      {a.staff_summary && (
        <Section label="Staff summary">
          <p className="text-sm">{a.staff_summary}</p>
        </Section>
      )}
      {a.customer_reply && (
        <Section label="Customer messages (simulated)">
          <div className="space-y-3">
            <div>
              <div className="mns-section-label mb-1">Acknowledgement</div>
              <p className="text-sm text-mns-mute whitespace-pre-line">{a.customer_reply}</p>
            </div>
            {a.reward_followup && (
              <div className="border-t border-mns-line pt-3">
                <div className="mns-section-label mb-1">Reward eligibility follow-up</div>
                <p className="text-sm text-mns-mute whitespace-pre-line">{a.reward_followup}</p>
              </div>
            )}
          </div>
        </Section>
      )}
      {a.trace && (
        <Section label="How this was analysed">
          <PipelineTrace trace={a.trace} />
        </Section>
      )}
      {a.aspects.length > 0 && !a.trace && (
        <Section label="Aspect analysis">
          <ul className="space-y-1.5">
            {a.aspects.map((asp, i) => (
              <li key={`${asp.aspect}-${i}`} className="flex items-start gap-3 text-sm">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs min-w-20 justify-center ${
                    asp.sentiment === 'positive'
                      ? 'bg-mns-success/10 text-mns-success'
                      : asp.sentiment === 'negative'
                      ? 'bg-mns-danger/10 text-mns-danger'
                      : 'bg-mns-navy/10 text-mns-navy'
                  }`}
                >
                  {asp.sentiment}
                </span>
                <div className="flex-1">
                  <div className="font-medium capitalize">{asp.aspect.replace('_', ' ')}</div>
                  {asp.evidence && (
                    <div className="text-xs text-mns-mute italic mt-0.5">"{asp.evidence}"</div>
                  )}
                </div>
                {typeof asp.confidence === 'number' && asp.confidence > 0 && (
                  <span className="text-xs text-mns-mute shrink-0 mt-0.5">
                    {Math.round(asp.confidence * 100)}%
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}
      {(a.model || a.prompt_version) && (
        <div className="text-[11px] text-mns-mute">
          Model: {a.model ?? 'n/a'} · prompt v{a.prompt_version ?? 'n/a'}
          {a.overall_score !== null && <> · score {a.overall_score}</>}
          {a.genuine !== null && <> · genuine: {a.genuine ? 'yes' : 'no'}</>}
        </div>
      )}
    </>
  )
}

function TicketBlock({ ticket }: { ticket: NonNullable<FeedbackDetail['ticket']> }) {
  return (
    <Section label="Linked ticket">
      <div className="rounded-md border border-mns-line p-3 text-sm space-y-1">
        <div className="flex items-center gap-2">
          <TicketIcon className="w-4 h-4 text-mns-navy" />
          <span className="font-semibold">#{ticket.id}</span>
          <Badge variant={ticket.status === 'resolved' ? 'success' : 'warn'}>{ticket.status.replace('_', ' ')}</Badge>
          <Badge variant={ticket.priority === 'high' ? 'danger' : ticket.priority === 'medium' ? 'warn' : 'default'}>
            {ticket.priority}
          </Badge>
        </div>
        <div className="text-xs text-mns-mute">
          Opened {new Date(ticket.opened_at).toLocaleString()}
          {ticket.assignee && <> · Assignee: {ticket.assignee}</>}
          {ticket.closed_at && <> · Closed {new Date(ticket.closed_at).toLocaleString()}</>}
        </div>
        {ticket.resolution_notes && (
          <div className="text-sm mt-1">Resolution: {ticket.resolution_notes}</div>
        )}
      </div>
    </Section>
  )
}

function RewardBlock({ reward }: { reward: NonNullable<FeedbackDetail['reward']> }) {
  return (
    <Section label="Reward">
      <div className="rounded-md border border-mns-line p-3 text-sm">
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="w-4 h-4 text-mns-gold" />
          <span className="font-semibold">{fmtGBP(reward.amount_gbp)}</span>
          <Badge variant="gold">{reward.tier} tier</Badge>
          <Badge variant="success">Issued</Badge>
        </div>
        <div className="text-xs text-mns-mute">
          Created {new Date(reward.issued_at).toLocaleString()}
          {reward.decided_by && <> · {reward.status} by {reward.decided_by}</>}
          {reward.decided_at && <> on {new Date(reward.decided_at).toLocaleString()}</>}
        </div>
        {reward.decision_note && <div className="mt-1 text-sm">Note: {reward.decision_note}</div>}
      </div>
    </Section>
  )
}

function catVariant(category: string): 'default' | 'success' | 'warn' | 'danger' | 'gold' {
  switch (category) {
    case 'serious_complaint': return 'danger'
    case 'minor_complaint': return 'warn'
    case 'major_compliment': return 'success'
    case 'minor_compliment': return 'gold'
    default: return 'default'
  }
}

function sentVariant(s: string): 'default' | 'success' | 'danger' {
  if (s === 'positive') return 'success'
  if (s === 'negative') return 'danger'
  return 'default'
}
