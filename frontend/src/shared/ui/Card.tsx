import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean
}

/** 基础卡片容器：白底、细边框、柔和阴影。 */
const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ hover, className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'rounded-2xl border border-white/70 bg-white/86 shadow-[0_20px_70px_rgba(15,23,42,0.08)] backdrop-blur-xl',
        hover && 'transition-all duration-150 hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-[0_28px_90px_rgba(79,70,229,0.14)]',
        className,
      )}
      {...props}
    />
  ),
)
Card.displayName = 'Card'

export default Card
