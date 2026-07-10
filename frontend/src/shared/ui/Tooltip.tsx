import type { ReactNode } from 'react'
import * as RTooltip from '@radix-ui/react-tooltip'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
}

/** 悬浮提示。需在根部包裹 <RTooltip.Provider>，此处自带 Provider 便于独立使用。 */
export default function Tooltip({ content, children, side = 'top' }: TooltipProps) {
  return (
    <RTooltip.Provider delayDuration={200}>
      <RTooltip.Root>
        <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
        <RTooltip.Portal>
          <RTooltip.Content
            side={side}
            sideOffset={6}
            className="z-50 rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs text-white shadow-float data-[state=delayed-open]:animate-fade-in"
          >
            {content}
            <RTooltip.Arrow className="fill-slate-800" />
          </RTooltip.Content>
        </RTooltip.Portal>
      </RTooltip.Root>
    </RTooltip.Provider>
  )
}
