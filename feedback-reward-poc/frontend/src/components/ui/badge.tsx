import * as React from 'react'
import { cn } from '../../lib/cn'

type Variant = 'default' | 'success' | 'warn' | 'danger' | 'gold'

const styles: Record<Variant, string> = {
  default: 'bg-mns-navy/10 text-mns-navy',
  success: 'bg-mns-success/10 text-mns-success',
  warn: 'bg-mns-warn/10 text-mns-warn',
  danger: 'bg-mns-danger/10 text-mns-danger',
  gold: 'bg-mns-gold/15 text-mns-navy',
}

export function Badge({
  variant = 'default',
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  return <span className={cn('mns-chip', styles[variant], className)} {...props} />
}
