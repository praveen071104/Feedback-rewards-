import { useEffect, useState } from 'react'
import { Activity, ArrowRight, MessageSquareText, ShieldCheck, Smile, RefreshCw, FolderOpen } from 'lucide-react'
import './Analytics.css'

const sentiments = ['Positive', 'Neutral', 'Negative'] as const
type Sentiment = typeof sentiments[number]

export type FeedbackRecord = {
  feedbackId: string
  storeId: string
  store: { name: string; location: string }
  loyalCustomer: boolean
  feedback: string
  createdAt: number
  sentiment: Sentiment
  sentimentConfidence: number
  genuineFeedback: 'Yes' | 'No'
  rewardEligible: boolean
  rewardDecision: 'eligible' | 'not_eligible' | 'pending'
}

const timeLabel = (timestamp: number) => new Date(timestamp).toLocaleTimeString([], {
  hour: '2-digit', minute: '2-digit',
})

export default function Analytics({ records, loading, error, hasMore, busy, onRefresh, onLoadMore, onOpen }: {
  records: FeedbackRecord[]
  loading: boolean
  error: string
  hasMore: boolean
  busy: boolean
  onRefresh: () => void
  onLoadMore: () => void
  onOpen: (id: string) => void
}) {
  const [sentiment, setSentiment] = useState('All')
  const [period, setPeriod] = useState('session')
  const [storeId, setStoreId] = useState('all')
  const [loyalty, setLoyalty] = useState('all')
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15000)
    return () => window.clearInterval(timer)
  }, [])

  const currentTime = Math.max(now, records[0]?.createdAt ?? now)
  const filtered = records.filter(record =>
    (storeId === 'all' || record.storeId === storeId) &&
    (loyalty === 'all' || record.loyalCustomer === (loyalty === 'loyal')) &&
    (sentiment === 'All' || record.sentiment === sentiment) &&
    (period === 'session' || record.createdAt >= currentTime - 3600000),
  )
  const counts = sentiments.map(label => ({ label, count: filtered.filter(record => record.sentiment === label).length }))
  const total = filtered.length
  const genuine = filtered.filter(record => record.genuineFeedback === 'Yes').length
  const percent = (count: number) => total ? `${Math.round(count / total * 100)}%` : '--'
  const bucketSize = 5 * 60000
  const lastBucket = Math.floor(currentTime / bucketSize) * bucketSize
  const buckets = Array.from({ length: 12 }, (_, index) => {
    const start = lastBucket - (11 - index) * bucketSize
    const entries = filtered.filter(record => record.createdAt >= start && record.createdAt < start + bucketSize)
    return { start, counts: sentiments.map(label => entries.filter(record => record.sentiment === label).length), total: entries.length }
  })
  const peak = Math.max(1, ...buckets.map(bucket => bucket.total))

  return (
    <div className="analytics">
      <div className="page-heading">
        <div>
          <p className="eyebrow">CUSTOMER EXPERIENCE / ANALYTICS</p>
          <h1>Insight engine</h1>
          <p className="analytics-subtitle">Saved analysis history</p>
        </div>
        <div className="session-status"><span className="status-dot" />Saved feedback · MongoDB</div>
      </div>
      <div className="analytics-toolbar">
        <div className="analytics-filters">
          <label>Time range
            <select value={period} onChange={event => setPeriod(event.target.value)}>
              <option value="session">All loaded history</option>
              <option value="hour">Last 60 minutes</option>
            </select>
          </label>
          <label>Sentiment filter
            <select value={sentiment} onChange={event => setSentiment(event.target.value)}>
              <option value="All">All sentiments</option>
              {sentiments.map(label => <option key={label}>{label}</option>)}
            </select>
          </label>
          <div className="history-filter"><label htmlFor="store-filter">Store filter</label>
            <select id="store-filter" value={storeId} onChange={event => setStoreId(event.target.value)}>
              <option value="all">All stores</option>
              {[...new Map(records.map(record => [record.storeId, record.store.name])).entries()].map(([id, name]) => <option value={id} key={id}>{name}</option>)}
            </select>
          </div>
          <div className="history-filter"><label htmlFor="loyalty-filter">Customer type</label>
            <select id="loyalty-filter" value={loyalty} onChange={event => setLoyalty(event.target.value)}>
              <option value="all">All customers</option><option value="loyal">Sparks Customers</option><option value="standard">Non-Sparks Customers</option>
            </select>
          </div>
        </div>
        <button className="icon-button" title="Refresh saved feedback" aria-label="Refresh saved feedback" disabled={loading} onClick={onRefresh}><RefreshCw size={18} /></button>
      </div>
      {loading && <p role="status">Loading saved feedback...</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="analytics-kpis" aria-live="polite">
        <div className="analytics-kpi"><span><MessageSquareText size={17} /> Analysed feedback</span><strong data-testid="analytics-total">{total}</strong><small>Successful analyses</small></div>
        <div className="analytics-kpi"><span><Smile size={17} /> Positive sentiment</span><strong>{percent(counts[0].count)}</strong><small>{counts[0].count} positive responses</small></div>
        <div className="analytics-kpi"><span><ShieldCheck size={17} /> Genuine feedback</span><strong>{percent(genuine)}</strong><small>{genuine} genuine / {total - genuine} not genuine</small></div>
        <div className="analytics-kpi"><span><Activity size={17} /> Reward eligible</span><strong>{filtered.filter(record => record.rewardEligible).length}</strong><small>Recommendations, not issued rewards</small></div>
      </div>
      {!records.length && !loading && !error ? (
        <section className="analytics-empty">
          <MessageSquareText size={32} />
          <h2>No analyses yet</h2>
          <a href="#feedback">Analyse feedback <ArrowRight size={17} /></a>
        </section>
      ) : records.length > 0 ? <>
        <div className="analytics-charts">
          <section className="distribution" aria-labelledby="distribution-heading">
            <div className="analytics-section-heading"><h2 id="distribution-heading">Sentiment distribution</h2><span>{total} responses</span></div>
            {counts.map(({ label, count }) => (
              <div className="distribution-row" key={label}>
                <div><span><i className={`sentiment-swatch ${label.toLowerCase()}`} />{label}</span><strong>{count} <small>{percent(count)}</small></strong></div>
                <div className="distribution-track" role="meter" aria-label={`${label} share`} aria-valuenow={total ? Math.round(count / total * 100) : 0} aria-valuemin={0} aria-valuemax={100}>
                  <span className={`chart-fill ${label.toLowerCase()}`} style={{ width: `${total ? count / total * 100 : 0}%` }} />
                </div>
              </div>
            ))}
          </section>
          <section className="activity-chart" aria-labelledby="activity-heading">
            <div className="analytics-section-heading"><h2 id="activity-heading">Recent activity</h2><span>5-minute intervals</span></div>
            <div className="activity-bars" role="img" aria-label={`Feedback volume by sentiment, from ${timeLabel(buckets[0].start)} to ${timeLabel(lastBucket + bucketSize)}. ${buckets.reduce((sum, bucket) => sum + bucket.total, 0)} analyses. Peak ${peak} per interval.`}>
              {buckets.map(bucket => (
                <div className="activity-column" key={bucket.start} title={`${timeLabel(bucket.start)}: ${sentiments.map((label, index) => `${bucket.counts[index]} ${label}`).join(', ')}`}>
                  <span className="activity-count">{bucket.total || ''}</span>
                  <div className="activity-stack">
                    {sentiments.map((label, index) => <span key={label} className={`chart-fill ${label.toLowerCase()}`} style={{ height: `${bucket.counts[index] / peak * 100}%` }} />)}
                  </div>
                </div>
              ))}
            </div>
            <div className="activity-axis"><span>{timeLabel(buckets[0].start)}</span><span>{timeLabel(lastBucket + bucketSize)}</span></div>
            <div className="chart-legend">{sentiments.map(label => <span key={label}><i className={`sentiment-swatch ${label.toLowerCase()}`} />{label}</span>)}</div>
          </section>
        </div>
        <section className="recent-feedback" aria-labelledby="recent-heading">
          <div className="analytics-section-heading"><h2 id="recent-heading">Recent feedback</h2><span>{total} loaded responses</span></div>
          {total === 0 ? <p className="no-matches">No feedback matches these filters.</p> : <div className="analytics-table-wrap" tabIndex={0} role="region" aria-label="Recent feedback results">
            <table>
              <thead><tr><th scope="col">Date / time</th><th scope="col">Feedback</th><th scope="col">Store</th><th scope="col">Customer</th><th scope="col">Sentiment</th><th scope="col">Genuine</th><th scope="col">Reward</th><th scope="col">Open</th></tr></thead>
              <tbody>{filtered.map(record => <tr key={record.feedbackId}>
                <td><time dateTime={new Date(record.createdAt).toISOString()}>{new Date(record.createdAt).toLocaleDateString()}<br />{timeLabel(record.createdAt)}</time></td>
                <td className="feedback-cell">{record.feedback}</td>
                <td>{record.store.name}<small className="probability">{record.store.location}</small></td>
                <td>{record.loyalCustomer ? 'Sparks Customer' : 'Non-Sparks Customer'}</td>
                <td><span className={`sentiment ${record.sentiment.toLowerCase()}`}>{record.sentiment}</span><small className="probability">{Math.round(record.sentimentConfidence * 100)}% model support</small></td>
                <td>{record.genuineFeedback}</td>
                <td>{record.rewardDecision === 'pending' ? 'Awaiting Colleague Review' : record.rewardEligible ? 'Eligible' : 'Not eligible'}</td>
                <td><button className="icon-button" aria-label={`Open feedback ${record.feedbackId}`} title="Open saved feedback" disabled={busy} onClick={() => onOpen(record.feedbackId)}><FolderOpen size={16} /></button></td>
              </tr>)}</tbody>
            </table>
          </div>}
        </section>
      </> : null}
      {hasMore && <button className="primary-button" disabled={loading} onClick={onLoadMore}>Load older feedback <ArrowRight size={17} /></button>}
      <p className="analytics-note">{records.length} saved records loaded. Totals and filters cover loaded history. Genuine means predicted usefulness, not verified authenticity. No rewards issued.</p>
    </div>
  )
}