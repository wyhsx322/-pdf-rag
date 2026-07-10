import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

/** 文本输入框：浅色极简，聚焦时靛紫描边。 */
const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm text-slate-800',
        'placeholder:text-slate-400 outline-none transition-colors',
        'focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/15',
        'disabled:cursor-not-allowed disabled:bg-slate-50 disabled:opacity-60',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export default Input
