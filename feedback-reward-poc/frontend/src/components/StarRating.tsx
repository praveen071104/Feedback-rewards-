import * as React from 'react'
import { Star } from 'lucide-react'

export function StarRating({
  value,
  onChange,
  disabled,
}: {
  value: number
  onChange: (v: number) => void
  disabled?: boolean
}) {
  const [hover, setHover] = React.useState<number | null>(null)
  const shown = hover ?? value
  return (
    <div className="flex items-center gap-1" role="radiogroup" aria-label="Star rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={disabled}
          onMouseEnter={() => setHover(n)}
          onMouseLeave={() => setHover(null)}
          onClick={() => onChange(n)}
          aria-label={`${n} star${n > 1 ? 's' : ''}`}
          aria-checked={value === n}
          role="radio"
          className="p-1 rounded hover:bg-mns-navy/5 disabled:cursor-not-allowed"
        >
          <Star
            className={`w-7 h-7 transition ${n <= shown ? 'fill-mns-gold text-mns-gold' : 'text-mns-navy/20'}`}
            strokeWidth={1.5}
          />
        </button>
      ))}
    </div>
  )
}
