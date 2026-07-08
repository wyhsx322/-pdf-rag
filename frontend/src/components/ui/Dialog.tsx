import type { ReactNode } from 'react'
import * as RDialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '../../lib/cn'

interface DialogProps {
  open: boolean
  onOpenChange: (v: boolean) => void
  title?: string
  description?: string
  children: ReactNode
  className?: string
}

/** 居中模态弹窗。 */
export default function Dialog({ open, onOpenChange, title, description, children, className }: DialogProps) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="fixed inset-0 z-50 bg-slate-900/30 backdrop-blur-sm data-[state=open]:animate-fade-in" />
        <RDialog.Content
          className={cn(
            'fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2',
            'rounded-2xl border border-slate-200 bg-white p-6 shadow-float',
            'focus:outline-none data-[state=open]:animate-fade-in',
            className,
          )}
        >
          {title && (
            <RDialog.Title className="text-base font-semibold text-slate-800">{title}</RDialog.Title>
          )}
          {description && (
            <RDialog.Description className="mt-1 text-sm text-slate-500">{description}</RDialog.Description>
          )}
          <RDialog.Close className="absolute right-4 top-4 rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600">
            <X className="h-4 w-4" />
          </RDialog.Close>
          <div className={cn(title && 'mt-4')}>{children}</div>
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  )
}
