import * as RSwitch from '@radix-ui/react-switch'
import { cn } from '../lib/cn'

interface SwitchProps {
  checked: boolean
  onCheckedChange: (v: boolean) => void
  label?: string
  disabled?: boolean
  className?: string
}

/** 开关：靛紫激活态。可选内联文字标签。 */
export default function Switch({ checked, onCheckedChange, label, disabled, className }: SwitchProps) {
  const sw = (
    <RSwitch.Root
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className={cn(
        'relative h-5 w-9 shrink-0 rounded-full transition-colors outline-none',
        'data-[state=unchecked]:bg-slate-200 data-[state=checked]:bg-gradient-to-r data-[state=checked]:from-indigo-500 data-[state=checked]:to-violet-500',
        'focus-visible:ring-2 focus-visible:ring-indigo-500/30 disabled:opacity-50',
        className,
      )}
    >
      <RSwitch.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[18px]" />
    </RSwitch.Root>
  )
  if (!label) return sw
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600">
      {sw}
      {label}
    </label>
  )
}
