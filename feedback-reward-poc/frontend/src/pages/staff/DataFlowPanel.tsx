import * as React from 'react'
import { ArrowDown, Database, FileText, Loader2, RefreshCw, Server, User } from 'lucide-react'
import { api, type DataFlowFollow, type DataFlowOverview } from '../../lib/api'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Badge } from '../../components/ui/badge'
import { Select } from '../../components/ui/input'

function Box({ icon, title, sub, tone = 'plain' }: { icon: React.ReactNode; title: string; sub: string; tone?: 'plain' | 'dark' | 'gold' }) {
  const cls =
    tone === 'dark' ? 'bg-mns-navy text-white' : tone === 'gold' ? 'bg-mns-cream border-mns-gold' : 'bg-white border-mns-line'
  return (
    <div className={`rounded-xl border p-3 ${cls}`}>
      <div className="flex items-center gap-2 text-sm font-semibold">{icon}{title}</div>
      <div className={`mt-0.5 text-xs ${tone === 'dark' ? 'text-white/70' : 'text-mns-mute'}`}>{sub}</div>
    </div>
  )
}

function Down() {
  return <ArrowDown className="mx-auto h-4 w-4 text-mns-gold" />
}

function Count({ n }: { n: number }) {
  return <span className="rounded-full bg-mns-gold/20 px-2 py-0.5 text-xs font-semibold text-mns-navy">{n.toLocaleString()}</span>
}

export default function DataFlowPanel() {
  const [data, setData] = React.useState<DataFlowOverview | null>(null)
  const [pick, setPick] = React.useState('')
  const [follow, setFollow] = React.useState<DataFlowFollow | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    setError(null)
    try {
      const d = await api.dataflow()
      setData(d)
      setPick((p) => p || d.recent[0]?.submission_id || '')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load')
    }
  }, [])

  React.useEffect(() => { load() }, [load])
  React.useEffect(() => {
    if (!pick) { setFollow(null); return }
    api.dataflowFollow(pick).then(setFollow).catch(() => setFollow(null))
  }, [pick])

  if (error) return <div className="text-mns-danger">{error}</div>
  if (!data) return <div className="flex justify-center py-20 text-mns-mute"><Loader2 className="h-5 w-5 animate-spin" /></div>

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-mns-navy">Data flow</h2>
          <p className="mt-0.5 text-sm text-mns-mute">Where each piece of feedback goes, and where it is stored. Counts are live.</p>
        </div>
        <Button variant="outline" size="sm" onClick={load}><RefreshCw className="h-4 w-4" /></Button>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>The journey of one review</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <Box icon={<User className="h-4 w-4 text-mns-gold" />} title="1. Customer form" sub="Customer submits stars, text, contact details and optional Sparks number" />
            <Down />
            <Box icon={<Server className="h-4 w-4 text-mns-gold" />} title="2. API checks it" sub="Email and 16-digit Sparks number are validated before anything is saved" />
            <Down />
            <Box tone="gold" icon={<Database className="h-4 w-4 text-mns-gold" />} title={`3. MongoDB: feedback`} sub="Saved exactly as sent, before analysis" />
            <Down />
            <Box tone="dark" icon={<Server className="h-4 w-4 text-mns-gold" />} title="4. Analyser" sub="Reads sentences, finds products and services, judges each, decides what happens next" />
            <Down />
            <Box tone="gold" icon={<Database className="h-4 w-4 text-mns-gold" />} title="5. MongoDB: analysis" sub="The decision, confidence and step-by-step trace" />
            <Down />
            <Box icon={<Database className="h-4 w-4 text-mns-navy" />} title="MongoDB collections" sub="Feedback, analysis, staff credentials, sessions, tickets, ticket history and rewards" />
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>MongoDB <span className="text-sm font-normal text-mns-mute">· documents</span></CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="text-xs text-mns-mute">Database <b className="text-mns-navy">{data.mongodb.database}</b> on {data.mongodb.host} {data.mongodb.ok ? <Badge variant="success">connected</Badge> : <Badge variant="danger">down</Badge>}</div>
              {data.mongodb.collections.map((c) => (
                <div key={c.name} className="flex items-start justify-between gap-3 text-sm">
                  <div><div className="font-medium">{c.name}</div><div className="text-xs text-mns-mute">{c.holds}</div></div>
                  <Count n={c.count} />
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Files on disk <span className="text-sm font-normal text-mns-mute">· model</span></CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {data.files.map((f) => (
                <div key={f.path} className="flex items-start justify-between gap-3 text-sm">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 font-medium"><FileText className="h-3.5 w-3.5 text-mns-mute" />{f.label}</div>
                    <div className="truncate font-mono text-xs text-mns-mute">{f.path}</div>
                  </div>
                  <div className="shrink-0 text-right text-xs text-mns-mute">
                    {f.exists ? <>{typeof f.rows === 'number' && <div className="font-semibold text-mns-navy">{f.rows.toLocaleString()} rows</div>}<div>{f.size_mb} MB</div></> : 'missing'}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle>Follow one submission</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <Select value={pick} onChange={(e) => setPick(e.target.value)} className="max-w-xl">
            {data.recent.length === 0 && <option value="">No feedback yet</option>}
            {data.recent.map((r) => (
              <option key={r.submission_id} value={r.submission_id}>{r.name ?? 'Anonymous'} · {r.text}</option>
            ))}
          </Select>
          {follow && (
            <ol className="space-y-3">
              {follow.steps.map((s) => (
                <li key={s.order} className="rounded-lg border border-mns-line bg-white p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-mns-navy text-[11px] font-semibold text-mns-gold">{s.order}</span>
                    <Badge variant={s.store === 'MongoDB' ? 'gold' : 'default'}>{s.store}</Badge>
                    <span className="font-mono text-xs text-mns-navy">{s.location}</span>
                    <span className="text-xs text-mns-mute">{s.what}</span>
                  </div>
                  {s.record ? (
                    <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-mns-cream p-2.5 text-[11px] leading-relaxed">{JSON.stringify(s.record, null, 2)}</pre>
                  ) : (
                    <p className="mt-2 text-xs italic text-mns-mute">{s.absent}</p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
