import * as React from 'react'
import { Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { api, type RewardQueueItem } from '../../lib/api'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import { Badge } from '../../components/ui/badge'
import { fmtGBP, fmtSparks } from '../../lib/format'

export default function RewardsQueue() {
  const [rows, setRows] = React.useState<RewardQueueItem[] | null>(null)
  const [loading, setLoading] = React.useState(false)

  const refresh = React.useCallback(async () => {
    setLoading(true)
    try {
      setRows(await api.listRewards())
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-mns-navy">Issued rewards</h2>
          <p className="text-sm text-mns-mute mt-0.5">
            Incentives confirmed and issued by a store colleague.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          </Button>
        </div>
      </header>

      {rows === null ? (
        <SkeletonList />
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="py-14 text-center text-mns-mute">
            No issued rewards yet.
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <RewardRow
              key={r.id}
              row={r}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function SkeletonList() {
  return (
    <ul className="space-y-3">
      {[0, 1, 2].map((i) => (
        <li key={i}>
          <Card>
            <CardContent className="p-5">
              <div className="h-3 w-32 bg-mns-navy/5 rounded mb-2" />
              <div className="h-3 w-full bg-mns-navy/5 rounded mb-1" />
              <div className="h-3 w-2/3 bg-mns-navy/5 rounded" />
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  )
}

function tierBadge(tier: RewardQueueItem['tier']) {
  const map = {
    high: { v: 'danger' as const, label: 'High' },
    mid: { v: 'warn' as const, label: 'Mid' },
    low: { v: 'default' as const, label: 'Low' },
  }
  return map[tier]
}

function statusBadge() {
  return { v: 'success' as const, label: 'Issued' }
}

function RewardRow({ row }: {
  row: RewardQueueItem
}) {
  const tier = tierBadge(row.tier)
  const st = statusBadge()

  return (
    <li>
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Sparkles className="w-4 h-4 text-mns-gold" />
            <span className="font-semibold text-mns-navy">
              {fmtGBP(row.amount_gbp)}
            </span>
            <Badge variant={tier.v}>Tier: {tier.label}</Badge>
            <Badge variant={st.v}>{st.label}</Badge>
            {row.category && (
              <Badge variant="gold">{row.category.replace('_', ' ')}</Badge>
            )}
            {row.sparks_member && (
              <Badge variant="default">Sparks{row.sparks_id ? ` ${fmtSparks(row.sparks_id)}` : ''}</Badge>
            )}
            <span className="ml-auto text-xs text-mns-mute">
              {new Date(row.issued_at).toLocaleString()}
            </span>
          </div>

          <div className="text-sm text-mns-mute">
            {row.customer_name && <>Customer: <span className="text-mns-ink">{row.customer_name}</span> • </>}
            {row.customer_email}
            {row.store_id && <> • Store: {row.store_id}</>}
            {typeof row.stars === 'number' && <> • {row.stars}/5</>}
          </div>

          {row.feedback && (
            <blockquote className="text-sm italic border-l-4 border-mns-gold/60 pl-3 py-1 bg-mns-cream/60 rounded-r">
              {row.feedback}
            </blockquote>
          )}

          {row.aspects && row.aspects.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
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

          <div className="text-xs text-mns-mute">
            {row.decided_by && <>Decided by {row.decided_by}</>}
            {row.decided_at && <> on {new Date(row.decided_at).toLocaleString()}</>}
            {row.decision_note && <div className="mt-1 text-mns-ink">Note: {row.decision_note}</div>}
          </div>
        </CardContent>
      </Card>
    </li>
  )
}
