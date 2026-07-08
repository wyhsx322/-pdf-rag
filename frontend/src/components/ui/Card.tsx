import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean
}

/** 基础卡片容器：白底、细边框、柔和阴影。 */
const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ hover, className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'rounded-2xl border border-slate-200/80 bg-white shadow-soft',
        hover && 'transition-all duration-150 hover:border-indigo-200 hover:shadow-float',
        className,
      )}
      {...props}
    />
  ),
)
Card.displayName = 'Card'

export default Card
