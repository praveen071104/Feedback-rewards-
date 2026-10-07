import * as React from 'react'
import { cn } from '../../lib/cn'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-md border border-mns-line bg-white px-3 text-sm shadow-sm',
        'placeholder:text-mns-mute/70',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mns-gold focus-visible:border-mns-gold',
        'disabled:opacity-60 disabled:cursor-not-allowed',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'min-h-[6rem] w-full rounded-md border border-mns-line bg-white px-3 py-2 text-sm shadow-sm',
        'placeholder:text-mns-mute/70',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mns-gold focus-visible:border-mns-gold',
        className,
      )}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'h-10 w-full rounded-md border border-mns-line bg-white px-3 text-sm shadow-sm',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mns-gold focus-visible:border-mns-gold',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
)
Select.displayName = 'Select'

export const Label = ({ className, ...p }: React.LabelHTMLAttributes<HTMLLabelElement>) => (
  <label className={cn('text-sm font-medium text-mns-ink', className)} {...p} />
)
