import { ArrowRight, CheckCircle2, Circle, Gift, ShieldAlert, Ticket as TicketIcon } from 'lucide-react'
import type { Trace } from '../lib/api'
import { Badge } from './ui/badge'

const SENT_STYLE = {
  positive: 'bg-mns-success/10 text-mns-success',
  negative: 'bg-mns-danger/10 text-mns-danger',
  neutral: 'bg-mns-navy/10 text-mns-navy',
} as const

const CATEGORY_LABEL: Record<string, string> = {
  minor_compliment: 'Compliment',
  major_compliment: 'Strong praise',
  minor_complaint: 'Complaint',
  serious_complaint: 'Serious complaint',
  gibberish: 'Not feedback',
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="grid grid-cols-[auto_1fr] gap-3">
      <span className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-mns-navy text-xs font-semibold text-mns-gold">
        {n}
      </span>
      <div className="min-w-0">
        <h5 className="text-sm font-semibold text-mns-navy">{title}</h5>
        <div className="mt-1.5 text-sm">{children}</div>
      </div>
    </li>
  )
}

/** Shows, in plain English, each step the analyser took on a review. */
export function PipelineTrace({ trace }: { trace: Trace }) {
  return (
    <ol className="space-y-4">
      <Step n={1} title="Read the review in sentences">
        <p className="text-mns-mute">
          The review is split so each point is judged on its own. The {trace.stars_used}-star rating is also taken into account.
        </p>
      </Step>

      <Step n={2} title="Match each sentence to a product or service, then judge it">
        <ul className="space-y-2">
          {trace.sentences.map((s, i) => (
            <li key={i} className="rounded-md border border-mns-line bg-white p-2.5">
              <p className="italic text-mns-ink">&ldquo;{s.sentence}&rdquo;</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
                <ArrowRight className="h-3 w-3 text-mns-mute" />
                {s.aspect && s.sentiment ? (
                  <>
                    <span className="font-medium capitalize text-mns-navy">{s.aspect.replace(/_/g, ' ')}</span>
                    <span className={`rounded-full px-2 py-0.5 ${SENT_STYLE[s.sentiment]}`}>{s.sentiment}</span>
                    {typeof s.confidence === 'number' && (
                      <span className="text-mns-mute">{Math.round(s.confidence * 100)}% sure</span>
                    )}
                  </>
                ) : (
                  <span className="text-mns-mute">{s.note}</span>
                )}
                {s.aspect && s.note && <span className="text-mns-warn">{s.note}</span>}
              </div>
            </li>
          ))}
        </ul>
      </Step>

      <Step n={3} title="Decide what kind of feedback it is">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="gold">{CATEGORY_LABEL[trace.category] ?? trace.category}</Badge>
          <span className="text-xs text-mns-mute">{Math.round(trace.category_confidence * 100)}% sure</span>
          {trace.review_flag && <Badge variant="warn">colleague should read this</Badge>}
        </div>
        <p className="mt-1.5 text-mns-mute">{trace.category_reason}</p>
      </Step>

      <Step n={4} title="Check there is enough detail">
        {trace.detail ? (
          <>
            <ul className="space-y-1">
              {trace.detail.checks.map((c) => (
                <li key={c.key} className="flex items-center gap-2">
                  {c.met ? <CheckCircle2 className="h-4 w-4 text-mns-success" /> : <Circle className="h-4 w-4 text-mns-mute" />}
                  <span className={c.met ? '' : 'text-mns-mute'}>{c.label}</span>
                </li>
              ))}
            </ul>
            <p className="mt-1.5 text-xs text-mns-mute">
              {trace.detail.detailed
                ? 'All four met, so this can be acted on and considered for a reward.'
                : 'A reward needs all four. The customer is asked for what is missing.'}
            </p>
          </>
        ) : (
          <p className="text-mns-mute">Not recorded for this review.</p>
        )}
      </Step>

      <Step n={5} title="Decide what happens next">
        <ul className="space-y-1.5">
          <li className="flex items-start gap-2">
            {trace.ticket.opened ? (
              <TicketIcon className="mt-0.5 h-4 w-4 text-mns-warn" />
            ) : (
              <CheckCircle2 className="mt-0.5 h-4 w-4 text-mns-success" />
            )}
            <span>
              <span className="font-medium">{trace.ticket.opened ? 'Ticket opened' : 'No ticket'}</span>
              <span className="text-mns-mute"> &middot; {trace.ticket.reason}</span>
            </span>
          </li>
          <li className="flex items-start gap-2">
            {trace.reward.tier === 'none' ? (
              <ShieldAlert className="mt-0.5 h-4 w-4 text-mns-mute" />
            ) : (
              <Gift className="mt-0.5 h-4 w-4 text-mns-gold" />
            )}
            <span>
              <span className="font-medium">
                {trace.reward.tier === 'none'
                  ? 'No reward'
                  : `${trace.reward.tier} tier${typeof trace.reward.amount_gbp === 'number' ? ` · £${trace.reward.amount_gbp.toFixed(2)}` : ''}, backend suggestion for colleague review`}
              </span>
              <span className="text-mns-mute"> &middot; {trace.reward.reason}</span>
            </span>
          </li>
        </ul>
      </Step>
    </ol>
  )
}
