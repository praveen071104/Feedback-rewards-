import { useEffect, useRef, useState } from 'react'

export const stores = [
  { id: 'unspecified', name: 'Not specified' },
  { id: 'marble-arch', name: 'M&S Marble Arch - London' },
  { id: 'stratford-city', name: 'M&S Stratford City - London' },
  { id: 'bluewater', name: 'M&S Bluewater - Greenhithe, Kent' },
]
export const statuses = ['Opened', 'In Progress', 'Resolved'] as const
export const decisions = ['Reward Eligible', 'Not Eligible', 'Awaiting Colleague Review'] as const
export type CaseStatus = typeof statuses[number]
export type Decision = typeof decisions[number]
export type Template = 'reward_eligible' | 'not_eligible' | 'general'
export type FeedbackCase = {
  case_id: string
  customer_id: string
  store_id: string
  feedback: string
  rating: number
  case_status: CaseStatus
  version: number
  created_at: string
  updated_at: string
  sentiment: { label: 'Positive' | 'Neutral' | 'Negative'; confidence: number; model_name: string; model_version: string; confidence_kind: string; rating_sentiment?: 'Positive' | 'Neutral' | 'Negative' | null; rating_conflict?: boolean }
  reward_assessment: {
    model_recommendation: Decision; model_confidence: number; model_label: string; model_name: string; model_version: string
    threshold: number; reason_code: string; model_reason: string; category: string; incentive_tier: string
    final_decision: Decision | null; decision_reason: string | null; confirmed_by: string | null; confirmed_at: string | null
  }
  notification: { is_read: boolean }
  customer_communication: { channel: string | null; template: Template | null; message: string | null; status: string; is_simulated: boolean; sent_at: string | null }
  activity_history: { action: string; timestamp: string; note?: string; colleague?: string; template?: Template; channel?: string }[]
}
export type CaseDetail = FeedbackCase & {
  customer: { name: string; email: string | null; phone_number: string | null; is_sparks_customer: boolean; sparks_id: string | null }
  communication_templates: Record<Template, string>
}
export type CasePage = { items: FeedbackCase[]; total: number; page: number; page_size: number }
export type Insights = { total: number; statuses: Record<string, number>; decisions: Record<string, number>; sentiments: Record<string, number>; average_rating: number | null; unread_count: number }
export type Notifications = { unread_count: number; revision: number; items: { case_id: string; store_id: string; created_at: string; is_read: boolean }[] }

export async function caseApi<Result>(path: string, options: RequestInit = {}): Promise<Result> {
  try {
    const timeout = AbortSignal.timeout(20000)
    const response = await fetch(`/api/${path}`, { ...options, signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout, headers: { 'Content-Type': 'application/json', ...options.headers } })
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const message = typeof data?.detail === 'string' ? data.detail : Array.isArray(data?.detail)
        ? data.detail.map((issue: { msg: string }) => issue.msg).join(' ') : 'Unable to save or load feedback. Please retry.'
      throw new Error(message)
    }
    if (!data) throw new Error('Unexpected server response. Please retry.')
    return data as Result
  } catch (error) {
    if (error instanceof TypeError) throw new Error('Cannot reach the server. Your changes have been kept. Please retry.')
    if (error instanceof DOMException && error.name === 'TimeoutError') throw new Error('Request timed out. Please retry the same action.')
    throw error
  }
}

export function useCaseNotifications() {
  const [notifications, setNotifications] = useState<Notifications>({ unread_count: 0, revision: 0, items: [] })
  const [error, setError] = useState('')
  const sequence = useRef(0)
  useEffect(() => {
    const controller = new AbortController()
    let socket: WebSocket | undefined
    let reconnect: ReturnType<typeof setTimeout> | undefined
    let disposed = false
    async function load() {
      const request = ++sequence.current
      try {
        const data = await caseApi<Notifications>('colleague/notifications', { signal: controller.signal })
        if (!disposed && sequence.current === request) { setNotifications(data); setError('') }
      } catch { if (!disposed && sequence.current === request) setError('Notifications unavailable. Retrying automatically.') }
    }
    function connect() {
      socket = new WebSocket(`${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/colleague/events`)
      socket.onmessage = () => void load()
      socket.onerror = () => socket?.close()
      socket.onclose = () => { if (!disposed) reconnect = setTimeout(connect, 10000) }
    }
    const start = setTimeout(connect, 0)
    void load()
    const poll = setInterval(() => void load(), 10000)
    const focus = () => void load()
    window.addEventListener('focus', focus)
    window.addEventListener('feedback-cases-refresh', focus)
    return () => {
      disposed = true; controller.abort(); socket?.close(); clearInterval(poll); clearTimeout(reconnect); clearTimeout(start)
      window.removeEventListener('focus', focus)
      window.removeEventListener('feedback-cases-refresh', focus)
    }
  }, [])
  return { notifications, error, refresh: () => window.dispatchEvent(new Event('feedback-cases-refresh')) }
}