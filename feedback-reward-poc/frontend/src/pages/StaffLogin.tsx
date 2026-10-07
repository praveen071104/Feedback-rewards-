import * as React from 'react'
import { Loader2, LogIn, UserPlus } from 'lucide-react'
import { api, type AuthStatus } from '../lib/api'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input, Label } from '../components/ui/input'

export default function StaffLogin({
  status,
  onAuthed,
}: {
  status: AuthStatus
  onAuthed: () => void
}) {
  const setupMode = status.setup_required
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (setupMode) await api.setupAdmin(username, password)
      else await api.login(username, password)
      onAuthed()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-md mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>{setupMode ? 'Create admin account' : 'Staff sign in'}</CardTitle>
          <CardDescription>
            {setupMode
              ? 'First-time setup. Choose a username and a password of at least 12 characters.'
              : 'Enter your staff credentials.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <div>
              <Label htmlFor="u">Username</Label>
              <Input
                id="u"
                autoFocus
                minLength={3}
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mt-1.5"
              />
            </div>
            <div>
              <Label htmlFor="p">Password</Label>
              <Input
                id="p"
                type="password"
                minLength={setupMode ? 12 : 1}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5"
              />
            </div>
            {error && (
              <div className="rounded-md bg-mns-danger/10 text-mns-danger text-sm px-3 py-2">{error}</div>
            )}
            <Button type="submit" variant="primary" className="w-full" disabled={busy}>
              {busy ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : setupMode ? (
                <>
                  <UserPlus className="w-4 h-4" /> Create and sign in
                </>
              ) : (
                <>
                  <LogIn className="w-4 h-4" /> Sign in
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
