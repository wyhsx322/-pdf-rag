import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

/** 多行文本框。 */
const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-800',
        'placeholder:text-slate-400 outline-none transition-colors resize-none',
        'focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/15',
        'disabled:cursor-not-allowed disabled:bg-slate-50 disabled:opacity-60',
        className,
      )}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'

export default Textarea
