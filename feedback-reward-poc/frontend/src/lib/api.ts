export type Store = { id: string; name: string }

export const DEFAULT_STORES: Store[] = [
  { id: 'marble-arch', name: 'Marble Arch' },
  { id: 'stratford-city', name: 'Stratford City' },
  { id: 'bluewater', name: 'Bluewater' },
  { id: 'unspecified', name: 'Not specified' },
]

export type FeedbackPayload = {
  name: string
  email: string
  phone?: string
  store_id: string
  stars: number
  feedback: string
  sparks_member: boolean
  sparks_id?: string | null
}

export type Reward = { tier: 'none' | 'low' | 'mid' | 'high'; amount_gbp: number; status: string }
export type RewardEligibility = {
  suggested_tier: 'none' | 'low' | 'mid' | 'high'
  suggested_amount_gbp: number
  tier: 'none' | 'low' | 'mid' | 'high' | null
  eligible: boolean | null
  decided_by: string | null
  decided_at: string | null
  note: string | null
}

export type FeedbackResult = {
  submission_id: string
  category: 'minor_compliment' | 'gibberish' | 'minor_complaint' | 'serious_complaint' | 'major_compliment'
  customer_reply: string
  reward_followup: string | null
  reward: Reward
  ticket_id: number | null
  needs_more_detail?: boolean
}

export type AuthStatus = { setup_required: boolean; authenticated: boolean; username: string | null }

export type Ticket = {
  id: number
  submission_id: string
  category: string
  priority: 'low' | 'medium' | 'high'
  status: 'open' | 'in_progress' | 'resolved'
  assignee: string | null
  store_id: string | null
  customer_name: string | null
  customer_email: string | null
  summary: string
  opened_at: string
  closed_at: string | null
  resolution_notes: string | null
}

export type TicketEvent = {
  id: number
  event_type: string
  actor: string
  note: string | null
  created_at: string
}

export type Aspect = { aspect: string; sentiment: 'positive' | 'negative' | 'neutral'; score: number; confidence?: number; evidence: string }

export type DetailCheck = { detailed: boolean; level: 'detailed' | 'some' | 'vague'; checks: Array<{ key: string; label: string; met: boolean }>; missing: string[] }

export type Trace = {
  sentences: Array<{
    sentence: string
    aspect: string | null
    sentiment: 'positive' | 'negative' | 'neutral' | null
    confidence: number | null
    note: string
  }>
  category: string
  category_confidence: number
  category_reason: string
  stars_used: number
  detail?: DetailCheck
  ticket: { opened: boolean; reason: string }
  reward: { tier: string; reason: string; amount_gbp?: number }
  review_flag: boolean
}

export type AnalysisResult = {
  category: string
  category_confidence: number
  needs_review: boolean
  reward_tier: string
  needs_ticket: boolean
  priority: string
  customer_reply: string
  aspects: Aspect[]
  trace: Trace
}

export type TicketDetail = Ticket & {
  events: TicketEvent[]
  customer_reply: string | null
  reward_followup: string | null
  feedback: string | null
  stars: number | null
  sparks_member: boolean | null
  sparks_id: string | null
  aspects: Aspect[] | null
  overall_sentiment: string | null
  overall_score: number | null
}

export type RecentFeedback = {
  submission_id: string
  customer_name: string | null
  customer_email: string | null
  sparks_member: boolean | null
  sparks_id: string | null
  store_id: string | null
  stars: number | null
  text: string
  created_at: string
  category: string | null
  category_confidence: number | null
  needs_review: boolean | null
  reward_tier: string | null
  needs_ticket: boolean | null
  priority: string | null
  overall_sentiment: string | null
  aspects: Aspect[]
}

export type FeedbackDetail = {
  submission_id: string
  customer: {
    name: string | null
    email: string | null
    phone: string | null
    sparks_member: boolean | null
    sparks_id: string | null
  }
  store_id: string | null
  stars: number | null
  text: string
  created_at: string
  reward_eligibility: RewardEligibility
  analysis: {
    category: string | null
    category_confidence: number | null
    needs_review: boolean | null
    genuine: boolean | null
    has_sufficient_detail: boolean | null
    reward_tier: string | null
    needs_ticket: boolean | null
    priority: string | null
    customer_reply: string | null
    reward_followup: string | null
    staff_summary: string | null
    overall_sentiment: string | null
    overall_score: number | null
    aspects: Aspect[]
    trace?: Trace | null
    model: string | null
    prompt_version: string | null
  }
  ticket: {
    id: number
    status: string
    priority: string
    assignee: string | null
    opened_at: string
    closed_at: string | null
    resolution_notes: string | null
  } | null
  reward: {
    id: number
    tier: string
    amount_gbp: number
    status: string
    decided_by: string | null
    decided_at: string | null
    decision_note: string | null
    issued_at: string
  } | null
}

export type DataFlowOverview = {
  mongodb: { ok: boolean; database: string; host: string; collections: Array<{ name: string; holds: string; count: number }> }
  files: Array<{ label: string; path: string; exists: boolean; size_mb?: number; rows?: number }>
  model: { backend: string }
  recent: Array<{ submission_id: string; name: string | null; text: string; created_at: string }>
}

export type DataFlowStep = {
  order: number
  store: 'MongoDB'
  location: string
  what: string
  record: Record<string, unknown> | Array<Record<string, unknown>> | null
  absent?: string
}

export type DataFlowFollow = { submission_id: string; steps: DataFlowStep[] }

export type Insights = {
  total_feedback: number
  by_category: Record<string, number>
  by_store: Record<string, number>
  open_tickets: number
  resolved_tickets: number
  total_rewards_issued: number
  total_gbp_issued: number
  has_more_recent: boolean
  recent: RecentFeedback[]
}

export type RewardQueueItem = {
  id: number
  submission_id: string
  customer_name: string | null
  customer_email: string | null
  store_id: string | null
  stars: number | null
  sparks_member: boolean | null
  sparks_id: string | null
  feedback: string | null
  category: string | null
  aspects: Aspect[]
  tier: 'low' | 'mid' | 'high'
  amount_gbp: number
  status: 'issued'
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  issued_at: string
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    ...init,
  }).catch(() => {
    throw new Error('The service is currently unavailable. Please try again.')
  })
  if (res.status >= 500) {
    throw new Error('The service is currently unavailable. Please try again.')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status} ${detail}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export type TicketFilters = {
  status?: string
  store_id?: string
  priority?: string
  category?: string
}

function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== '')
  if (entries.length === 0) return ''
  return '?' + new URLSearchParams(entries.map(([key, value]) => [key, String(value)])).toString()
}

export const api = {
  stores: () => request<Store[]>('/api/stores')
    .then((stores) => Array.isArray(stores) && stores.length > 0 ? stores : DEFAULT_STORES)
    .catch(() => DEFAULT_STORES),
  submitFeedback: (p: FeedbackPayload) =>
    request<FeedbackResult>('/api/feedback', { method: 'POST', body: JSON.stringify(p) }),

  authStatus: () => request<AuthStatus>('/api/auth/status'),
  setupAdmin: (username: string, password: string) =>
    request<{ username: string }>('/api/auth/setup', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  login: (username: string, password: string) =>
    request<{ username: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),

  listTickets: (f: TicketFilters = {}) =>
    request<Ticket[]>('/api/staff/tickets' + qs({
      status_filter: f.status,
      store_id: f.store_id,
      priority: f.priority,
      category: f.category,
    })),
  getTicket: (id: number) => request<TicketDetail>(`/api/staff/tickets/${id}`),
  updateTicket: (
    id: number,
    body: Partial<{ status: string; assignee: string; resolution_notes: string; note: string }>,
  ) =>
    request<Ticket>(`/api/staff/tickets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  insights: (store_id?: string, limit_recent: number = 20, offset: number = 0) =>
    request<Insights>('/api/staff/insights' + qs({ store_id, limit_recent, offset })),
  getFeedbackDetail: (submissionId: string) =>
    request<FeedbackDetail>(`/api/staff/feedback/${submissionId}`),
  decideRewardEligibility: (submissionId: string, tier: RewardEligibility['suggested_tier'], note?: string) =>
    request<RewardEligibility>(`/api/staff/feedback/${submissionId}/reward-eligibility`, {
      method: 'PATCH',
      body: JSON.stringify({ tier, note }),
    }),
  analyse: (feedback: string, stars: number, sparks_member: boolean = false) =>
    request<AnalysisResult>('/api/staff/analyse', {
      method: 'POST',
      body: JSON.stringify({ feedback, stars, sparks_member }),
    }),
  dataflow: () => request<DataFlowOverview>('/api/staff/dataflow'),
  dataflowFollow: (id: string) => request<DataFlowFollow>(`/api/staff/dataflow/${id}`),
  listRewards: () => request<RewardQueueItem[]>('/api/staff/rewards'),
}
