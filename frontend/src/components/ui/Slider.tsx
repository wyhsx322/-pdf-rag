import * as RSlider from '@radix-ui/react-slider'
import { cn } from '../../lib/cn'

interface SliderProps {
  value: number
  onValueChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  className?: string
}

/** 单值滑块。 */
export default function Slider({ value, onValueChange, min = 0, max = 100, step = 1, className }: SliderProps) {
  return (
    <RSlider.Root
      value={[value]}
      onValueChange={([v]) => onValueChange(v)}
      min={min}
      max={max}
      step={step}
      className={cn('relative flex h-5 w-full touch-none select-none items-center', className)}
    >
      <RSlider.Track className="relative h-1.5 w-full grow rounded-full bg-slate-200">
        <RSlider.Range className="absolute h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500" />
      </RSlider.Track>
      <RSlider.Thumb
        className="block h-4 w-4 rounded-full border-2 border-indigo-500 bg-white shadow outline-none transition-transform hover:scale-110 focus-visible:ring-2 focus-visible:ring-indigo-500/30"
        aria-label="value"
      />
    </RSlider.Root>
  )
}
