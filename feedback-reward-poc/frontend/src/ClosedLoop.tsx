import { useState } from 'react'
import { ArrowRight, Bell, Check, CircleCheck, ClipboardCheck, Clock3, Gift, MessageSquareText, QrCode, Search, Store, UserRound } from 'lucide-react'
import './ClosedLoop.css'

type Status = 'Awaiting details' | 'Open' | 'In progress' | 'Resolved' | 'Closed'
type Case = {
  id: string
  store: string
  customer: string
  category: string
  status: Status
  loyal?: boolean
  title: string
  feedback: string
  owner: string
  ticket: string | null
  incentive: 'None' | 'Tier-based' | 'High tier'
  action: string
  response: string
  next: string
  history: { at: string; event: string }[]
}

const initialCases: Case[] = [
  {
    id: 'CL-1042', store: 'Marble Arch', customer: 'Priya S.', category: 'Minor complaint', status: 'Resolved',
    title: 'Fitting-room lock repaired', owner: 'Alex Morgan · Facilities', ticket: 'TK-1042', incentive: 'None',
    feedback: 'The lock on fitting room 3 would not close on Tuesday. I had to hold the door while trying on a dress.',
    action: 'Replaced the faulty latch in fitting room 3. The duty manager tested all six fitting-room locks before reopening the room.',
    response: 'We are sorry you could not use the fitting room comfortably. We have replaced the lock and checked the other rooms. Thank you for helping us put this right.',
    next: 'Completed 24 Sep, 10:15. Customer update recorded in this sample.',
    history: [
      { at: '22 Sep, 14:05', event: 'Store QR feedback received; colleague alert recorded.' },
      { at: '22 Sep, 14:12', event: 'Apology recorded. Ticket opened and assigned to Alex Morgan.' },
      { at: '23 Sep, 09:20', event: 'Replacement latch fitted; all fitting-room locks checked.' },
      { at: '24 Sep, 10:15', event: 'Customer update recorded. Issue resolved and loop closed.' },
    ],
  },
  {
    id: 'CL-1043', store: 'Stratford City', customer: 'Daniel R.', category: 'Serious complaint', status: 'In progress',
    title: 'Duplicate payment under review', owner: 'Maya Patel · Customer care', ticket: 'TK-1043', incentive: 'Tier-based',
    feedback: 'My card was charged twice for a £64 order yesterday. Both payments have cleared and I am out of pocket.',
    action: 'Priority ticket assigned to Maya. A customer callback is recorded; the receipts and both payment references are with the payments team.',
    response: 'We are sincerely sorry for the duplicate charge. Maya is your named contact and will keep you updated while our payments team investigates.',
    next: 'Confirm the duplicate transaction and agree the refund with the customer. Incentive tier awaits review.',
    history: [
      { at: '24 Sep, 09:10', event: 'Store QR feedback received; priority colleague alert recorded.' },
      { at: '24 Sep, 09:18', event: 'Sincere apology recorded. Maya assigned as customer contact.' },
      { at: '24 Sep, 10:00', event: 'Customer callback recorded; payment evidence sent for review.' },
    ],
  },
  {
    id: 'CL-1044', store: 'Marble Arch', customer: 'Amira K.', category: 'Minor complaint', status: 'Awaiting details',
    title: 'More detail needed about a queue', owner: 'Customer service desk', ticket: null, incentive: 'None',
    feedback: 'The queue was too slow.',
    action: 'Apology and a request for the visit time and checkout location recorded. No ticket opened yet.',
    response: 'We are sorry about the wait. Could you share when you visited and which checkout you used so we can look into it?',
    next: 'Await customer details, then open a ticket and record the follow-up action.',
    history: [
      { at: '24 Sep, 10:25', event: 'Store QR feedback received.' },
      { at: '24 Sep, 10:30', event: 'Apology and request for details recorded; ticket deferred.' },
    ],
  },
  {
    id: 'CL-1045', store: 'Bluewater', customer: 'Helen T.', category: 'Major compliment', status: 'Closed',
    title: 'Exceptional help recognised', owner: 'Sam Ellis · Store manager', ticket: null, incentive: 'Tier-based',
    feedback: 'Your colleague went above and beyond, locating the jacket I needed for an interview and arranging collection from another store that afternoon.',
    action: 'Personal thanks recorded for Helen. Recognition shared with the colleague and store manager. Tier-based incentive recommended, not issued.',
    response: 'Thank you for explaining how our colleague helped with your interview outfit. We have shared your recognition with the team and hope the interview went well.',
    next: 'Acknowledgement complete. Incentive amount and fulfilment remain undecided.',
    history: [
      { at: '23 Sep, 11:40', event: 'Store QR feedback received and reviewed as a major compliment.' },
      { at: '23 Sep, 12:15', event: 'Contextual thanks recorded; colleague recognition shared.' },
      { at: '23 Sep, 12:20', event: 'Feedback loop closed. Tier-based incentive recommendation recorded.' },
    ],
  },
  {
    id: 'CL-1046', store: 'Stratford City', customer: 'Jess L.', category: 'Minor compliment', status: 'Closed',
    title: 'Baby clothes appreciation acknowledged', owner: 'Customer service desk', ticket: null, incentive: 'None',
    feedback: 'Baby clothes are lovely quality and wash well. I bought loads for my newborn.',
    action: 'A contextual thank-you recorded. No complaint ticket or incentive needed.',
    response: 'Thank you for sharing that the baby clothes are washing well. We are glad you are enjoying them, and congratulations on your newborn.',
    next: 'Thank-you complete. Feedback loop closed.',
    history: [
      { at: '24 Sep, 08:50', event: 'Store QR compliment received.' },
      { at: '24 Sep, 08:51', event: 'Contextual thanks recorded. Loop closed without a ticket.' },
    ],
  },
  {
    id: 'CL-1047', store: 'Bluewater', customer: 'Ravi M.', category: 'Minor complaint', status: 'Resolved', loyal: true,
    title: 'Shelf prices made clearer', owner: 'Sam Ellis · Store manager', ticket: 'TK-1047', incentive: 'High tier',
    feedback: 'I shop here every week. The shelf labels beside the meal deals are too small to read and the offer price is not clear.',
    action: 'Replaced the meal-deal shelf labels with larger print and checked that each offer shows its full price. High-tier incentive recommended for a loyal customer with genuine feedback.',
    response: 'Thank you for shopping with us regularly and pointing out the labels. We have replaced them with larger, clearer prices and checked the display.',
    next: 'Completed 24 Sep, 09:45. High-tier incentive recommendation awaits fulfilment policy.',
    history: [
      { at: '23 Sep, 16:05', event: 'Store QR feedback received; sample loyalty profile marked as loyal.' },
      { at: '23 Sep, 16:20', event: 'Genuine issue reviewed; ticket assigned to Sam.' },
      { at: '24 Sep, 09:45', event: 'Labels replaced and checked. Customer update recorded; loop closed.' },
    ],
  },
  {
    id: 'CL-1048', store: 'Marble Arch', customer: 'Leo B.', category: 'Minor complaint', status: 'Open',
    title: 'Empty hand-soap dispenser', owner: 'Alex Morgan · Facilities', ticket: 'TK-1048', incentive: 'None',
    feedback: 'The soap dispenser next to the left sink in the customer toilets was empty at 10am today.',
    action: 'Apology recorded and a facilities ticket opened with the location and visit time.',
    response: 'We are sorry the dispenser was empty. We have passed the exact location to our facilities colleague to check and refill it.',
    next: 'Check the dispenser, refill it and record the completed action.',
    history: [
      { at: '24 Sep, 10:10', event: 'Store QR feedback received; colleague alert recorded.' },
      { at: '24 Sep, 10:14', event: 'Apology recorded; ticket opened and assigned to facilities.' },
    ],
  },
]

const storeLocations: Record<string, string> = {
  'Marble Arch': 'London',
  'Stratford City': 'London',
  'Bluewater': 'Greenhithe, Kent',
}

const rules = [
  ['Minor compliment', 'Contextual thanks; close the loop', 'None'],
  ['Gibberish', 'Ignore; no ticket or customer reply', 'None'],
  ['Minor complaint', 'Apologise; ticket when details suffice; record action', 'None by default'],
  ['Serious complaint', 'Apologise; priority ticket, owner and customer contact', 'Tier-based'],
  ['Major compliment', 'Thank customer; recognise the contribution', 'Tier-based'],
  ['Loyal + genuine feedback', 'Respond to the feedback; loyalty takes precedence', 'High tier'],
]

const isClosed = (item: Case) => item.status === 'Resolved' || item.status === 'Closed'
const statusClass = (status: Status) => status.toLowerCase().replaceAll(' ', '-')

export default function ClosedLoop() {
  const [cases, setCases] = useState(initialCases)
  const [store, setStore] = useState('All stores')
  const [status, setStatus] = useState('All statuses')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState(initialCases[0].id)
  const [resolution, setResolution] = useState('')
  const [notice, setNotice] = useState('')
  const storeCases = cases.filter(item => store === 'All stores' || item.store === store)
  const filtered = storeCases.filter(item =>
    (status === 'All statuses' || item.status === status) &&
    `${item.id} ${item.title} ${item.customer} ${item.feedback}`.toLowerCase().includes(query.toLowerCase()),
  )
  const selected = filtered.find(item => item.id === selectedId) ?? filtered[0]
  const closedCount = storeCases.filter(isClosed).length

  function updateCase(item: Case, nextStatus: Status, action: string) {
    const at = new Date().toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
    setCases(current => current.map(entry => entry.id !== item.id ? entry : {
      ...entry, status: nextStatus, action,
      response: nextStatus === 'Resolved' ? `Thank you for raising this. We have completed the following action: ${action}` : entry.response,
      next: nextStatus === 'Resolved' ? `Completed ${at}. Simulated customer update recorded; no message sent.` : 'Record the verified action before closing this case.',
      history: [...entry.history, { at, event: nextStatus === 'Resolved' ? `${action} Simulated customer update recorded; loop closed.` : 'Assigned colleague started work on the issue.' }],
    }))
    setResolution('')
    setNotice(`${item.id}: ${nextStatus === 'Resolved' ? 'resolution and simulated customer update recorded.' : 'work started.'}`)
  }

  return <div className="closed-loop">
    <div className="page-heading">
      <div><p className="eyebrow">STORE EXPERIENCE / FOLLOW-THROUGH</p><h1>Closed Loop</h1></div>
      <div className="loop-demo"><span className="status-dot" />Sample cases · Demo only<span>No live alerts, messages or incentives</span></div>
    </div>
    <div className="loop-metrics" aria-label="Store case totals">
      <div><span><MessageSquareText size={17} />Feedback cases</span><strong>{storeCases.length}</strong><small>Meaningful store feedback</small></div>
      <div><span><ClipboardCheck size={17} />Loops closed</span><strong>{closedCount}<small> / {storeCases.length}</small></strong><small>Resolved or acknowledged</small></div>
      <div><span><Clock3 size={17} />Awaiting action</span><strong>{storeCases.length - closedCount}</strong><small>Details, review or resolution</small></div>
      <div><span><Gift size={17} />Incentives proposed</span><strong>{storeCases.filter(item => item.incentive !== 'None').length}</strong><small>Recommendations only</small></div>
    </div>
    <div className="loop-toolbar">
      <div><label htmlFor="loop-store">Store</label><select id="loop-store" value={store} onChange={event => { setStore(event.target.value); setResolution('') }}><option>All stores</option>{Object.entries(storeLocations).map(([name, location]) => <option key={name} value={name}>M&amp;S {name} - {location}</option>)}</select></div>
      <div><label htmlFor="loop-status">Case status</label><select id="loop-status" value={status} onChange={event => { setStatus(event.target.value); setResolution('') }}><option>All statuses</option>{['Awaiting details', 'Open', 'In progress', 'Resolved', 'Closed'].map(name => <option key={name}>{name}</option>)}</select></div>
      <div className="loop-search"><label htmlFor="loop-search">Search cases</label><span><Search size={17} /><input id="loop-search" type="search" value={query} onChange={event => { setQuery(event.target.value); setResolution('') }} placeholder="Case, customer or issue" /></span></div>
    </div>
    <p className="loop-notice" role="status">{notice}</p>
    {selected ? <div className="loop-workspace">
      <aside className="loop-case-list" aria-label="Feedback cases">
        <div className="loop-list-heading"><h2>Store feedback</h2><span>{filtered.length} cases</span></div>
        {filtered.map(item => <button key={item.id} className={`loop-case ${item.id === selected.id ? 'selected' : ''}`} aria-pressed={item.id === selected.id}
          onClick={() => { setSelectedId(item.id); setResolution(''); setNotice('') }}>
          <span className="loop-case-meta"><span>{item.id}</span><span className={`loop-status ${statusClass(item.status)}`}>{item.status}</span></span>
          <strong>{item.title}</strong><span className="loop-case-store"><Store size={13} /><span>M&amp;S {item.store} - {storeLocations[item.store]}</span></span>
          <span className="loop-case-category">{item.loyal ? 'Loyal customer + genuine feedback' : item.category}</span>
        </button>)}
      </aside>
      <section className="loop-detail" aria-labelledby="case-title">
        <div className="loop-detail-heading"><span>{selected.id} / {selected.store}</span><span className={`loop-status ${statusClass(selected.status)}`}>{selected.status}</span></div>
        <h2 id="case-title">{selected.title}</h2>
        <div className="loop-person"><UserRound size={15} />{selected.customer}<span>{selected.loyal ? 'Loyal customer · Genuine feedback' : selected.category}</span></div>
        <ol className="loop-stages" aria-label="Case progress">
          <li className="complete"><QrCode size={19} /><span>Store QR</span></li>
          <li className="complete"><Bell size={19} /><span>Received</span></li>
          <li className={selected.status === 'Awaiting details' ? '' : 'complete'}><ClipboardCheck size={19} /><span>Action</span></li>
          <li className={isClosed(selected) ? 'complete' : ''}><CircleCheck size={19} /><span>Loop closed</span></li>
        </ol>
        <div className="loop-outcome">
          <div><h3><MessageSquareText size={17} />You said</h3><blockquote>{selected.feedback}</blockquote></div>
          <div className={isClosed(selected) ? 'loop-done' : ''}><h3>{isClosed(selected) ? <Check size={18} /> : <Clock3 size={18} />}{isClosed(selected) ? 'We did' : 'Action so far'}</h3><p>{selected.action}</p></div>
        </div>
        <dl className="loop-ownership">
          <div><dt>Store location</dt><dd>M&amp;S {selected.store} - {storeLocations[selected.store]}</dd></div>
          <div><dt>Responsible colleague</dt><dd>{selected.owner}</dd></div>
          <div><dt>Ticket</dt><dd>{selected.ticket ?? (selected.status === 'Awaiting details' ? 'Awaiting details' : 'Not required')}</dd></div>
          <div><dt>Incentive recommendation</dt><dd><Gift size={15} />{selected.incentive}{selected.incentive !== 'None' && <small>Not issued · Amount undecided</small>}</dd></div>
        </dl>
        <section className="loop-message" aria-label="Customer update"><h3>Customer update <span>Simulated</span></h3><p>{selected.response}</p></section>
        <section className="loop-timeline" aria-label="Action history"><h3>Action history</h3><ol>{selected.history.map((event, index) => <li key={`${event.at}-${index}`}><span className="loop-event-dot" /><div><span>{event.at}</span><p>{event.event}</p></div></li>)}</ol></section>
        <div className="loop-next"><strong>{isClosed(selected) ? 'Outcome' : 'Next step'}</strong><p>{selected.next}</p></div>
        {selected.status === 'Open' && <button className="primary-button loop-action" onClick={() => updateCase(selected, 'In progress', 'Assigned colleague is checking the reported issue.')}><ArrowRight size={17} />Start work (demo)</button>}
        {selected.status === 'In progress' && <form className="loop-resolution" onSubmit={event => { event.preventDefault(); if (resolution.trim().length >= 12) updateCase(selected, 'Resolved', resolution.trim()) }}>
          <label htmlFor="resolution">Completed action</label><textarea id="resolution" value={resolution} onChange={event => setResolution(event.target.value)} required minLength={12} maxLength={1000} placeholder="Record what was fixed and checked" />
          <button className="primary-button loop-action" disabled={resolution.trim().length < 12}><CircleCheck size={17} />Record resolution (demo)</button>
        </form>}
      </section>
    </div> : <section className="loop-empty"><Search size={28} /><h2>No matching cases</h2><button className="primary-button loop-action" onClick={() => { setStore('All stores'); setStatus('All statuses'); setQuery('') }}>Clear filters</button></section>}
    <section className="loop-policy" aria-labelledby="policy-title"><div><h2 id="policy-title">Response & incentive policy</h2><span>1 gibberish sample ignored · No ticket, reply or incentive</span></div>
      <div className="loop-policy-table" role="region" aria-label="Six-category policy" tabIndex={0}><table><thead><tr><th>Feedback</th><th>Follow-through</th><th>Incentive</th></tr></thead><tbody>{rules.map(([category, action, incentive]) => <tr key={category}><th scope="row">{category}</th><td>{action}</td><td>{incentive}</td></tr>)}</tbody></table></div>
    </section>
  </div>
}