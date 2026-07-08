import * as RTabs from '@radix-ui/react-tabs'
import { cn } from '../../lib/cn'

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
      <RTabs.List className={cn('inline-flex items-center gap-1 rounded-xl bg-slate-100 p-1', className)}>
        {items.map(it => (
          <RTabs.Trigger
            key={it.value}
            value={it.value}
            className={cn(
              'rounded-lg px-3.5 py-1.5 text-sm font-medium text-slate-500 transition-all outline-none',
              'data-[state=active]:bg-white data-[state=active]:text-indigo-600 data-[state=active]:shadow-soft',
            )}
          >
            {it.label}
          </RTabs.Trigger>
        ))}
      </RTabs.List>
    </RTabs.Root>
  )
}
