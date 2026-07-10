import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
type Size = 'sm' | 'md' | 'lg' | 'icon'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const variants: Record<Variant, string> = {
  primary:
    'bg-slate-950 text-white shadow-[0_14px_34px_rgba(15,23,42,0.18)] hover:bg-indigo-600 hover:shadow-[0_18px_46px_rgba(79,70,229,0.24)]',
  secondary:
    'bg-white/80 text-slate-700 ring-1 ring-slate-200 hover:bg-white hover:ring-indigo-200',
  ghost:
    'text-slate-500 hover:bg-white/70 hover:text-slate-900',
  danger:
    'bg-rose-500 text-white hover:bg-rose-600 shadow-soft',
  outline:
    'border border-slate-200 bg-white/70 text-slate-600 hover:border-indigo-300 hover:bg-white hover:text-indigo-600',
}

const sizes: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-lg',
  md: 'h-10 px-4 text-sm gap-2 rounded-xl',
  lg: 'h-12 px-6 text-base gap-2 rounded-xl',
  icon: 'h-9 w-9 rounded-lg',
}

/** 通用按钮：靛紫渐变主色，含 loading 态。 */
const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, className, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center font-medium transition-all duration-150 outline-none',
        'focus-visible:ring-2 focus-visible:ring-indigo-500/30',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none disabled:brightness-100',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  ),
)
Button.displayName = 'Button'

export default Button
