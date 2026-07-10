import { Loader2 } from 'lucide-react'
import { cn } from '../lib/cn'

/** 加载旋转图标。 */
export default function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('h-5 w-5 animate-spin text-indigo-500', className)} />
}
