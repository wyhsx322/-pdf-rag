import * as RTabs from '@radix-ui/react-tabs'
import { cn } from '../lib/cn'

export interface TabItem {
  value: string
  label: string
}

interface TabsProps {
  value: string
  onValueChange: (v: string) => void
  items: TabItem[]
  className?: string
}

/** 分段标签栏（受控）。 */
export default function Tabs({ value, onValueChange, items, className }: TabsProps) {
  return (
    <RTabs.Root value={value} onValueChange={onValueChange}>
      <RTabs.List className={cn('inline-flex items-center gap-1 rounded-2xl border border-white/80 bg-white/60 p-1 shadow-soft backdrop-blur', className)}>
        {items.map(it => (
          <RTabs.Trigger
            key={it.value}
            value={it.value}
            className={cn(
              'rounded-xl px-4 py-2 text-sm font-medium text-slate-500 transition-all outline-none',
              'data-[state=active]:bg-slate-950 data-[state=active]:text-white data-[state=active]:shadow-soft',
            )}
          >
            {it.label}
          </RTabs.Trigger>
        ))}
      </RTabs.List>
    </RTabs.Root>
  )
}
