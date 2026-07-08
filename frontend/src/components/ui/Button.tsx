import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
type Size = 'sm' | 'md' | 'lg' | 'icon'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const variants: Record<Variant, string> = {
  primary:
    'bg-gradient-to-r from-indigo-500 to-violet-500 text-white shadow-soft hover:shadow-glow hover:brightness-105',
  secondary:
    'bg-slate-100 text-slate-700 hover:bg-slate-200',
  ghost:
    'text-slate-500 hover:bg-slate-100 hover:text-slate-800',
  danger:
    'bg-rose-500 text-white hover:bg-rose-600 shadow-soft',
  outline:
    'border border-slate-200 bg-white text-slate-600 hover:border-indigo-300 hover:text-indigo-600',
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
