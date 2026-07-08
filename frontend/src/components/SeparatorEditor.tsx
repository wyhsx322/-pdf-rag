import { ChevronUp, ChevronDown, X } from 'lucide-react'
import Select from './ui/Select'

interface Props {
  separators: string[]
  onChange: (separators: string[]) => void
}

const DISPLAY: Record<string, string> = {
  '\n\n': '双换行 (段落)', '\n': '单换行', '。': '中文句号 (。)', '.': '英文句号 (.)',
  '！': '中文感叹号 (！)', '？': '中文问号 (？)', '；': '中文分号 (；)', ';': '英文分号 (;)',
  ' ': '空格', '': '逐字符',
}
const PRESETS = ['\n\n', '\n', '。', '.', '！', '？', '；', ';', ' ', '']

// Radix Select 不接受空字符串 value，用哨兵代表「逐字符」分隔符
const EMPTY = '__char__'

export default function SeparatorEditor({ separators, onChange }: Props) {
  const add = (raw: string) => {
    const sep = raw === EMPTY ? '' : raw
    if (!separators.includes(sep)) onChange([...separators, sep])
  }
  const remove = (i: number) => onChange(separators.filter((_, idx) => idx !== i))
  const move = (i: number, dir: 'up' | 'down') => {
    const next = [...separators]
    const t = dir === 'up' ? i - 1 : i + 1
    if (t < 0 || t >= next.length) return
    ;[next[i], next[t]] = [next[t], next[i]]
    onChange(next)
  }

  const options = PRESETS.filter(p => !separators.includes(p)).map(p => ({ value: p === '' ? EMPTY : p, label: DISPLAY[p] ?? JSON.stringify(p) }))

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        {separators.map((sep, i) => (
          <div key={i} className="group flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-1.5">
            <span className="w-4 shrink-0 text-xs font-medium text-slate-400">{i + 1}</span>
            <span className="flex-1 font-mono text-sm text-slate-600">{DISPLAY[sep] ?? JSON.stringify(sep)}</span>
            <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
              <button onClick={() => move(i, 'up')} disabled={i === 0} className="rounded p-1 text-slate-400 hover:bg-slate-200 disabled:opacity-30"><ChevronUp className="h-3.5 w-3.5" /></button>
              <button onClick={() => move(i, 'down')} disabled={i === separators.length - 1} className="rounded p-1 text-slate-400 hover:bg-slate-200 disabled:opacity-30"><ChevronDown className="h-3.5 w-3.5" /></button>
              <button onClick={() => remove(i)} className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-500"><X className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ))}
      </div>
      {options.length > 0 && (
        <Select value="" onValueChange={add} options={options} placeholder="添加分隔符…" className="h-9 w-full" />
      )}
    </div>
  )
}
