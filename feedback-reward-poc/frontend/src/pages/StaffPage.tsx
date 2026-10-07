import * as React from 'react'
import { LogOut, Loader2, RefreshCw } from 'lucide-react'
import { api, type AuthStatus } from '../lib/api'
import { Button } from '../components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import StaffLogin from './StaffLogin'
import TicketQueue from './staff/TicketQueue'
import RewardsQueue from './staff/RewardsQueue'
import InsightsPanel from './staff/InsightsPanel'
import AnalyserPanel from './staff/AnalyserPanel'
import DataFlowPanel from './staff/DataFlowPanel'

type Tab = 'queue' | 'rewards' | 'insights' | 'analyser' | 'dataflow'

export default function StaffPage() {
  const [status, setStatus] = React.useState<AuthStatus | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [tab, setTab] = React.useState<Tab>('queue')

  const refresh = React.useCallback(() => {
    setError(null)
    api.authStatus().then(setStatus).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Unable to connect. Please try again.')
    })
  }, [])

  React.useEffect(refresh, [refresh])

  if (error) {
    return (
      <div className="space-y-4 py-12 text-center">
        <p role="alert" className="text-sm text-mns-danger">{error}</p>
        <Button variant="outline" onClick={refresh}>
          <RefreshCw className="h-4 w-4" /> Retry
        </Button>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="flex items-center justify-center py-20 text-mns-mute">
        <Loader2 className="w-5 h-5 animate-spin" />
      </div>
    )
  }

  if (!status.authenticated) {
    return <StaffLogin status={status} onAuthed={refresh} />
  }

  async function doLogout() {
    await api.logout()
    refresh()
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display text-mns-navy">Store Colleague Hub</h1>
          <p className="text-mns-mute text-sm mt-1">Signed in as {status.username}</p>
        </div>
        <Button variant="outline" onClick={doLogout}>
          <LogOut className="w-4 h-4" /> Sign out
        </Button>
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList className="flex flex-wrap justify-start">
          <TabsTrigger value="queue">Tickets</TabsTrigger>
          <TabsTrigger value="rewards">Rewards</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
          <TabsTrigger value="analyser">Analyser</TabsTrigger>
          <TabsTrigger value="dataflow">Data flow</TabsTrigger>
        </TabsList>
        <TabsContent value="queue" className="mt-6">
          <TicketQueue />
        </TabsContent>
        <TabsContent value="rewards" className="mt-6">
          <RewardsQueue />
        </TabsContent>
        <TabsContent value="insights" className="mt-6">
          <InsightsPanel />
        </TabsContent>
        <TabsContent value="analyser" className="mt-6">
          <AnalyserPanel />
        </TabsContent>
        <TabsContent value="dataflow" className="mt-6">
          <DataFlowPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}
