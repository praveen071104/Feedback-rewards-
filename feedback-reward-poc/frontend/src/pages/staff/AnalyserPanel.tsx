import * as React from 'react'
import { Loader2, Wand2 } from 'lucide-react'
import { api, type AnalysisResult } from '../../lib/api'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { Textarea } from '../../components/ui/input'
import { StarRating } from '../../components/StarRating'
import { PipelineTrace } from '../../components/PipelineTrace'

const EXAMPLES: Array<{ label: string; text: string; stars: number }> = [
  { label: 'Mixed', text: 'The Colin the Caterpillar cake was amazing, but the sizing on the trousers was completely off.', stars: 3 },
  { label: 'Sarcasm', text: 'Oh brilliant, another long queue at the till. Just what I needed today.', stars: 1 },
  { label: 'Sparks', text: 'My Sparks digital wallet balance was glitchy and the offer would not apply.', stars: 2 },
  { label: 'Serious', text: 'I found glass in my sandwich from the food hall yesterday.', stars: 1 },
  { label: 'Praise', text: 'The Per Una dress is true to size and the fabric is lovely.', stars: 5 },
]

export default function AnalyserPanel() {
  const [text, setText] = React.useState(EXAMPLES[0].text)
  const [stars, setStars] = React.useState(EXAMPLES[0].stars)
  const [sparksMember, setSparksMember] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [result, setResult] = React.useState<AnalysisResult | null>(null)

  async function run() {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.analyse(text, stars, sparksMember))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-xl font-semibold text-mns-navy">Analyser</h2>
        <p className="mt-0.5 text-sm text-mns-mute">
          Type any review to see, step by step, how it would be read. Nothing is saved.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Try a review</CardTitle>
            <CardDescription>Pick an example or write your own.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex.label}
                  onClick={() => {
                    setText(ex.text)
                    setStars(ex.stars)
                  }}
                  className="rounded-full border border-mns-line bg-white px-3 py-1 text-xs font-medium text-mns-navy hover:border-mns-gold"
                >
                  {ex.label}
                </button>
              ))}
            </div>
            <Textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} />
            <label htmlFor="analyse-sparks-member" className="flex items-center gap-2 text-sm text-mns-navy">
              <input
                id="analyse-sparks-member"
                type="checkbox"
                checked={sparksMember}
                onChange={(e) => setSparksMember(e.target.checked)}
                className="h-4 w-4 accent-mns-navy"
              />
              Sparks member
            </label>
            <div className="flex items-center justify-between gap-3">
              <StarRating value={stars} onChange={setStars} />
              <Button variant="gold" onClick={run} disabled={busy || !text.trim()}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
                Analyse
              </Button>
            </div>
            {error && <div className="rounded-md bg-mns-danger/10 px-3 py-2 text-sm text-mns-danger">{error}</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>How it was analysed</CardTitle>
          </CardHeader>
          <CardContent>
            {result ? (
              <>
                <PipelineTrace trace={result.trace} />
                <div className="mt-5 rounded-md border border-mns-gold/40 bg-mns-cream p-3">
                  <div className="mns-section-label mb-1">Reply the customer would see</div>
                  <p className="text-sm whitespace-pre-line">{result.customer_reply}</p>
                </div>
              </>
            ) : (
              <p className="py-10 text-center text-mns-mute">Press Analyse to see the steps.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
