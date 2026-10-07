import * as React from 'react'
import { AlertTriangle, CheckCircle2, Clock, Filter, Loader2, RefreshCw, Ticket as TicketIcon, X } from 'lucide-react'
import { api, DEFAULT_STORES, type Store, type Ticket, type TicketDetail, type TicketFilters } from '../../lib/api'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Input, Label, Select, Textarea } from '../../components/ui/input'
import { Badge } from '../../components/ui/badge'
import { fmtSparks } from '../../lib/format'

const STATUSES = ['open', 'in_progress', 'resolved'] as const
const PRIORITIES = ['low', 'medium', 'high'] as const
const CATEGORIES = ['minor_compliment', 'major_compliment', 'minor_complaint', 'serious_complaint'] as const

export default function TicketQueue() {
  const [tickets, setTickets] = React.useState<Ticket[] | null>(null)
  const [stores, setStores] = React.useState<Store[]>(DEFAULT_STORES)
  const [filters, setFilters] = React.useState<TicketFilters>({})
  const [selected, setSelected] = React.useState<TicketDetail | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const activeCount = Object.values(filters).filter(Boolean).length

  React.useEffect(() => {
    api.stores().then(setStores)
  }, [])

  const refresh = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await api.listTickets(filters)
      setTickets(list)
      if (selected) {
        const fresh = await api.getTicket(selected.id).catch(() => null)
        if (fresh) setSelected(fresh)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load tickets. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [filters, selected])

  React.useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])

  async function openTicket(id: number) {
    try {
      setError(null)
      const t = await api.getTicket(id)
      setSelected(t)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load this ticket. Please try again.')
    }
  }

  function setFilter<K extends keyof TicketFilters>(k: K, v: string) {
    setFilters((prev) => ({ ...prev, [k]: v || undefined }))
  }

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-semibold text-mns-navy">Tickets</h2>
          {activeCount > 0 && (
            <Badge variant="gold" className="flex items-center gap-1">
              <Filter className="w-3 h-3" /> {activeCount}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeCount > 0 && (
            <Button variant="ghost" size="sm" onClick={() => setFilters({})}>
              <X className="w-4 h-4" /> Clear
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading} aria-label="Refresh tickets" title="Refresh tickets">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          </Button>
        </div>
      </header>

      <Card>
        <CardContent className="p-3 grid gap-2 grid-cols-2 sm:grid-cols-4">
          <FilterField label="Status">
            <Select value={filters.status ?? ''} onChange={(e) => setFilter('status', e.target.value)} className="h-9">
              <option value="">All</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </Select>
          </FilterField>
          <FilterField label="Priority">
            <Select value={filters.priority ?? ''} onChange={(e) => setFilter('priority', e.target.value)} className="h-9">
              <option value="">All</option>
              {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
          </FilterField>
          <FilterField label="Store">
            <Select aria-label="Store" value={filters.store_id ?? ''} onChange={(e) => setFilter('store_id', e.target.value)} className="h-9">
              <option value="">All</option>
              {stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </FilterField>
          <FilterField label="Category">
            <Select value={filters.category ?? ''} onChange={(e) => setFilter('category', e.target.value)} className="h-9">
              <option value="">All</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
            </Select>
          </FilterField>
        </CardContent>
      </Card>

      {error && <p role="alert" className="text-sm text-mns-danger">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2 space-y-2 max-h-[70vh] overflow-y-auto pr-1">
          {tickets === null && !error && <SkeletonList />}
          {tickets && tickets.length === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-mns-mute">No tickets match your filters.</CardContent>
            </Card>
          )}
          {tickets?.map((t) => (
            <button
              key={t.id}
              onClick={() => openTicket(t.id)}
              className={`w-full text-left transition rounded-xl2 ${
                selected?.id === t.id ? 'ring-inset ring-2 ring-mns-gold' : ''
              }`}
            >
              <Card className="hover:border-mns-gold/60">
                <CardContent className="p-4">
                  <div className="flex items-start gap-2">
                    <TicketIcon className="w-4 h-4 text-mns-navy mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-semibold text-mns-navy">#{t.id}</span>
                        <PriorityBadge p={t.priority} />
                        <StatusBadge s={t.status} />
                      </div>
                      <div className="text-sm line-clamp-2">{t.summary}</div>
                      <div className="text-xs text-mns-mute mt-1 flex items-center gap-2">
                        <span>{t.store_id ?? 'unspecified'}</span>
                        <span>•</span>
                        <span>{new Date(t.opened_at).toLocaleString()}</span>
                        {t.assignee && (
                          <>
                            <span>•</span>
                            <span>Assignee: {t.assignee}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </button>
          ))}
        </div>

        <div className="lg:col-span-3">
          {!selected ? (
            <Card>
              <CardContent className="py-20 text-center text-mns-mute">
                Select a ticket to see details and update it.
              </CardContent>
            </Card>
          ) : (
            <TicketDetailPanel detail={selected} onChanged={refresh} />
          )}
        </div>
      </div>
    </div>
  )
}

function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mns-section-label mb-1">{label}</div>
      {children}
    </div>
  )
}

function SkeletonList() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <div className="h-3 bg-mns-navy/5 rounded w-24 mb-2" />
            <div className="h-3 bg-mns-navy/5 rounded w-full mb-1" />
            <div className="h-3 bg-mns-navy/5 rounded w-2/3" />
          </CardContent>
        </Card>
      ))}
    </>
  )
}

function PriorityBadge({ p }: { p: Ticket['priority'] }) {
  const v = p === 'high' ? 'danger' : p === 'medium' ? 'warn' : 'default'
  return (
    <Badge variant={v} className="uppercase tracking-wider">
      {p}
    </Badge>
  )
}

function StatusBadge({ s }: { s: Ticket['status'] }) {
  const map: Record<Ticket['status'], { v: 'default' | 'warn' | 'success'; icon: React.ReactNode }> = {
    open: { v: 'warn', icon: <AlertTriangle className="w-3 h-3" /> },
    in_progress: { v: 'default', icon: <Clock className="w-3 h-3" /> },
    resolved: { v: 'success', icon: <CheckCircle2 className="w-3 h-3" /> },
  }
  const { v, icon } = map[s]
  return (
    <Badge variant={v} className="flex items-center gap-1">
      {icon} {s.replace('_', ' ')}
    </Badge>
  )
}

function AspectBadge({ sentiment }: { sentiment: 'positive' | 'negative' | 'neutral' | 'mixed' }) {
  const map = {
    positive: { v: 'success' as const, label: '+ positive' },
    negative: { v: 'danger' as const, label: '− negative' },
    neutral: { v: 'default' as const, label: '◦ neutral' },
    mixed: { v: 'warn' as const, label: 'mixed' },
  }
  const { v, label } = map[sentiment]
  return <Badge variant={v}>{label}</Badge>
}

function TicketDetailPanel({ detail, onChanged }: { detail: TicketDetail; onChanged: () => void }) {
  const [status, setStatus] = React.useState<Ticket['status']>(detail.status)
  const [assignee, setAssignee] = React.useState(detail.assignee ?? '')
  const [note, setNote] = React.useState('')
  const [resolution, setResolution] = React.useState(detail.resolution_notes ?? '')
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    setStatus(detail.status)
    setAssignee(detail.assignee ?? '')
    setNote('')
    setResolution(detail.resolution_notes ?? '')
  }, [detail.id])

  async function save() {
    setSaving(true)
    try {
      await api.updateTicket(detail.id, {
        status,
        assignee,
        resolution_notes: resolution,
        note: note || undefined,
      })
      setNote('')
      onChanged()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2 mb-1">
          <CardTitle>Ticket #{detail.id}</CardTitle>
          <PriorityBadge p={detail.priority} />
          <StatusBadge s={detail.status} />
        </div>
        <div className="text-sm text-mns-mute">
          {detail.customer_name && <>Customer: {detail.customer_name} • </>}
          {detail.customer_email}
          {detail.store_id && <> • Store: {detail.store_id}</>}
          {detail.sparks_member && (
            <> • <span className="text-mns-navy font-medium">Sparks</span>{detail.sparks_id ? ` ${fmtSparks(detail.sparks_id)}` : ''}</>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <section>
          <h4 className="mns-section-label mb-2">Summary</h4>
          <p className="text-sm">{detail.summary}</p>
        </section>

        {detail.feedback && (
          <section>
            <h4 className="mns-section-label mb-2">Customer feedback</h4>
            <blockquote className="text-sm italic border-l-4 border-mns-gold/60 pl-3 py-1 bg-mns-cream/60 rounded-r">
              {detail.feedback}
              {detail.stars && (
                <div className="not-italic text-xs text-mns-mute mt-1">Rating: {detail.stars}/5</div>
              )}
            </blockquote>
          </section>
        )}

        {detail.customer_reply && (
          <section>
            <h4 className="mns-section-label mb-2">Customer messages (simulated)</h4>
            <div className="space-y-3">
              <div>
                <div className="mns-section-label mb-1">Acknowledgement</div>
                <p className="text-sm text-mns-mute whitespace-pre-line">{detail.customer_reply}</p>
              </div>
              {detail.reward_followup && (
                <div className="border-t border-mns-line pt-3">
                  <div className="mns-section-label mb-1">Reward eligibility follow-up</div>
                  <p className="text-sm text-mns-mute whitespace-pre-line">{detail.reward_followup}</p>
                </div>
              )}
            </div>
          </section>
        )}

        {detail.aspects && detail.aspects.length > 0 && (
          <section>
            <h4 className="mns-section-label mb-2 flex items-center gap-2">
              <span>Aspects detected</span>
              {detail.overall_sentiment && (
                <span className="normal-case tracking-normal text-mns-ink font-normal">
                  overall:
                </span>
              )}
              {detail.overall_sentiment && (
                <AspectBadge sentiment={detail.overall_sentiment as 'positive' | 'negative' | 'neutral' | 'mixed'} />
              )}
            </h4>
            <ul className="space-y-1.5">
              {detail.aspects.map((a, i) => (
                <li key={`${a.aspect}-${i}`} className="flex items-center gap-2 text-sm">
                  <AspectBadge sentiment={a.sentiment} />
                  <span className="font-medium capitalize">{a.aspect.replace('_', ' ')}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label>Status</Label>
            <Select value={status} onChange={(e) => setStatus(e.target.value as Ticket['status'])} className="mt-1.5">
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace('_', ' ')}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Assignee</Label>
            <Input
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
              placeholder="Colleague name"
              className="mt-1.5"
            />
          </div>
        </section>

        <section>
          <Label>Add note</Label>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} className="mt-1.5" rows={2} />
        </section>

        <section>
          <Label>Resolution notes</Label>
          <Textarea
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            className="mt-1.5"
            rows={3}
            placeholder="Required when marking as resolved."
          />
        </section>

        <div className="flex items-center gap-2">
          <Button onClick={save} disabled={saving}>
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save update'}
          </Button>
          <span className="text-xs text-mns-mute">Opened {new Date(detail.opened_at).toLocaleString()}</span>
        </div>

        <section>
          <h4 className="mns-section-label mb-3">Activity</h4>
          <ol className="space-y-4">
            {detail.events.map((e, i) => (
              <li key={e.id} className="relative grid grid-cols-[auto_1fr] gap-3 items-start">
                {i < detail.events.length - 1 && (
                  <span
                    aria-hidden
                    className="absolute left-[5px] top-4 bottom-[-20px] w-px bg-mns-line"
                  />
                )}
                <span className="relative z-10 mt-1.5 w-2.5 h-2.5 rounded-full bg-mns-gold ring-4 ring-white" />
                <div className="min-w-0">
                  <div className="text-sm">
                    <span className="font-medium capitalize">{e.event_type.replace('_', ' ')}</span>
                    <span className="text-mns-mute"> by {e.actor} · {new Date(e.created_at).toLocaleString()}</span>
                  </div>
                  {e.note && <div className="text-sm text-mns-ink mt-0.5">{e.note}</div>}
                </div>
              </li>
            ))}
          </ol>
        </section>
      </CardContent>
    </Card>
  )
}
