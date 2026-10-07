import * as React from 'react'
import { Award, BarChart3, Loader2, MapPin, Mail, RefreshCw, Sparkles, Star, Ticket as TicketIcon, User } from 'lucide-react'
import { api, DEFAULT_STORES, type Insights, type RecentFeedback, type Store } from '../../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Select } from '../../components/ui/input'
import { FeedbackDetailDialog } from '../../components/FeedbackDetailDialog'
import { fmtGBP, fmtSparks } from '../../lib/format'

export default function InsightsPanel() {
  const [data, setData] = React.useState<Insights | null>(null)
  const [stores, setStores] = React.useState<Store[]>(DEFAULT_STORES)
  const [storeFilter, setStoreFilter] = React.useState<string>('')
  const [openSubmission, setOpenSubmission] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [revision, setRevision] = React.useState(0)
  const [loadingMore, setLoadingMore] = React.useState(false)

  React.useEffect(() => {
    api.stores().then(setStores)
  }, [])

  React.useEffect(() => {
    let active = true
    setData(null)
    setError(null)
    api.insights(storeFilter || undefined).then((next) => {
      if (active) setData(next)
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : 'Unable to load insights. Please try again.')
    })
    return () => { active = false }
  }, [storeFilter, revision])

  async function loadMore() {
    if (!data || loadingMore) return
    setLoadingMore(true)
    setError(null)
    try {
      const page = await api.insights(storeFilter || undefined, 20, data.recent.length)
      setData((current) => current ? { ...page, recent: [...current.recent, ...page.recent] } : page)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load more feedback.')
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-mns-navy">Insights</h2>
          <p className="text-sm text-mns-mute mt-0.5">Aggregated metrics across feedback, tickets and rewards.</p>
        </div>
        <label htmlFor="insights-store" className="flex items-center gap-2">
            <span className="text-xs uppercase tracking-wider text-mns-mute">Store</span>
            <Select
              id="insights-store"
              value={storeFilter}
              onChange={(e) => setStoreFilter(e.target.value)}
              className="h-9 w-48"
            >
              <option value="">All stores</option>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </Select>
        </label>
      </header>

      {error && (
        <div className="flex flex-wrap items-center gap-3">
          <p role="alert" className="text-sm text-mns-danger">{error}</p>
          <Button variant="outline" onClick={() => setRevision((value) => value + 1)}>
            <RefreshCw className="h-4 w-4" /> Retry
          </Button>
        </div>
      )}
      {!data && !error && <div className="flex items-center gap-2 py-12 text-mns-mute"><Loader2 className="h-4 w-4 animate-spin" /> Loading...</div>}
      {data && !error && <>
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat icon={<BarChart3 className="w-4 h-4" />} label="Feedback total" value={data.total_feedback} />
        <Stat
          icon={<TicketIcon className="w-4 h-4" />}
          label="Open tickets"
          value={data.open_tickets}
          hint={`${data.resolved_tickets} resolved`}
        />
        <Stat
          icon={<Award className="w-4 h-4" />}
          label="Rewards issued"
          value={data.total_rewards_issued}
        />
        <Stat icon={<Award className="w-4 h-4" />} label="Incentive value issued" value={fmtGBP(data.total_gbp_issued)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>By category</CardTitle>
          </CardHeader>
          <CardContent>
            <BarChart items={Object.entries(data.by_category)} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>By store</CardTitle>
          </CardHeader>
          <CardContent>
            <BarChart items={Object.entries(data.by_store)} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent feedback{storeFilter ? ` — ${storeFilter}` : ''}</CardTitle>
          <p className="text-xs text-mns-mute mt-1">Click any entry to see the full breakdown.</p>
        </CardHeader>
        <CardContent className="pt-0">
          {data.recent.length === 0 ? (
            <div className="py-6 text-center text-mns-mute">Nothing yet.</div>
          ) : (
            <ul className="divide-y divide-mns-line">
              {data.recent.map((r) => (
                <RecentRow
                  key={r.submission_id}
                  row={r}
                  onClick={() => setOpenSubmission(r.submission_id)}
                />
              ))}
            </ul>
          )}
          {data.has_more_recent && (
            <div className="flex justify-center border-t border-mns-line pt-4">
              <Button variant="outline" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Load more feedback
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <FeedbackDetailDialog
        submissionId={openSubmission}
        open={openSubmission !== null}
        onOpenChange={(v) => !v && setOpenSubmission(null)}
      />
      </>}
    </div>
  )
}

function RecentRow({ row, onClick }: { row: RecentFeedback; onClick: () => void }) {
  return (
    <li>
      <button
        onClick={onClick}
        className="w-full text-left py-4 px-1 -mx-1 rounded-md hover:bg-mns-navy/5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mns-gold"
      >
        <div className="flex flex-wrap items-center gap-2 mb-2">
          {row.category && (
            <Badge variant={categoryVariant(row.category)}>{row.category.replace('_', ' ')}</Badge>
          )}
          {typeof row.category_confidence === 'number' && (
            <span className="text-xs text-mns-mute">{Math.round(row.category_confidence * 100)}%</span>
          )}
          {row.needs_review && <Badge variant="warn">needs review</Badge>}
          {row.priority && row.priority !== 'low' && (
            <Badge variant={row.priority === 'high' ? 'danger' : 'warn'}>priority: {row.priority}</Badge>
          )}
          {row.reward_tier && row.reward_tier !== 'none' && (
            <Badge variant="gold" className="flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> {row.reward_tier} tier
            </Badge>
          )}
          {row.needs_ticket && (
            <Badge variant="warn" className="flex items-center gap-1">
              <TicketIcon className="w-3 h-3" /> ticket
            </Badge>
          )}
          <span className="ml-auto text-xs text-mns-mute">
            {new Date(row.created_at).toLocaleString()}
          </span>
        </div>

        <p className="text-sm text-mns-ink leading-relaxed">{row.text}</p>

        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-mns-mute">
          {row.customer_name && (
            <span className="flex items-center gap-1">
              <User className="w-3 h-3" /> {row.customer_name}
            </span>
          )}
          {row.customer_email && (
            <span className="flex items-center gap-1">
              <Mail className="w-3 h-3" /> {row.customer_email}
            </span>
          )}
          {row.store_id && (
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" /> {row.store_id}
            </span>
          )}
          {typeof row.stars === 'number' && (
            <span className="flex items-center gap-1">
              <Star className="w-3 h-3 fill-mns-gold text-mns-gold" /> {row.stars}/5
            </span>
          )}
          {row.sparks_member && (
            <span className="flex items-center gap-1 text-mns-navy font-medium">
              Sparks{row.sparks_id ? ` ${fmtSparks(row.sparks_id)}` : ''}
            </span>
          )}
        </div>

        {row.aspects.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {row.aspects.map((a, i) => (
              <span
                key={`${a.aspect}-${i}`}
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                  a.sentiment === 'positive'
                    ? 'bg-mns-success/10 text-mns-success'
                    : a.sentiment === 'negative'
                    ? 'bg-mns-danger/10 text-mns-danger'
                    : 'bg-mns-navy/10 text-mns-navy'
                }`}
              >
                {a.aspect.replace('_', ' ')} · {a.sentiment}
              </span>
            ))}
          </div>
        )}
      </button>
    </li>
  )
}

function categoryVariant(category: string): 'default' | 'success' | 'warn' | 'danger' | 'gold' {
  switch (category) {
    case 'serious_complaint': return 'danger'
    case 'minor_complaint': return 'warn'
    case 'major_compliment': return 'success'
    case 'minor_compliment': return 'gold'
    case 'gibberish': return 'default'
    default: return 'default'
  }
}

function Stat({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode
  label: string
  value: number | string
  hint?: string
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center gap-2 text-mns-mute text-xs uppercase tracking-wider">
          {icon} {label}
        </div>
        <div className="mt-1 text-3xl font-semibold text-mns-navy">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
        {hint && <div className="text-xs text-mns-mute mt-0.5">{hint}</div>}
      </CardContent>
    </Card>
  )
}

function BarChart({ items }: { items: Array<[string, number]> }) {
  const max = Math.max(1, ...items.map(([, v]) => v))
  if (items.length === 0) return <div className="text-sm text-mns-mute">No data.</div>
  return (
    <ul className="space-y-2">
      {items.map(([k, v]) => (
        <li key={k}>
          <div className="flex items-center justify-between text-sm">
            <span className="capitalize">{k.replace('_', ' ')}</span>
            <span className="font-medium">{v}</span>
          </div>
          <div className="h-2 bg-mns-navy/5 rounded">
            <div
              className="h-2 rounded bg-mns-gold"
              style={{ width: `${(v / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
