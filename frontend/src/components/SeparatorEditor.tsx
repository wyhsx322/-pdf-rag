import { useState } from 'react'

interface SeparatorEditorProps {
  separators: string[]
  onChange: (separators: string[]) => void
}

// 分隔符显示名称映射
const SEPARATOR_DISPLAY: Record<string, string> = {
  '\n\n': '双换行 (段落)',
  '\n': '单换行',
  '。': '中文句号 (。)',
  '.': '英文句号 (.)',
  '！': '中文感叹号 (！)',
  '？': '中文问号 (？)',
  '；': '中文分号 (；)',
  ';': '英文分号 (;)',
  ' ': '空格',
  '': '逐字符',
}

export default function SeparatorEditor({ separators, onChange }: SeparatorEditorProps) {
  const [newSep, setNewSep] = useState('')

  // 可用的预设分隔符
  const presets = ['\n\n', '\n', '。', '.', '！', '？', '；', ';', ' ', '']

  const addSeparator = (sep: string) => {
    if (!separators.includes(sep)) {
      onChange([...separators, sep])
    }
    setNewSep('')
  }

  const removeSeparator = (index: number) => {
    onChange(separators.filter((_, i) => i !== index))
  }

  const moveSeparator = (index: number, direction: 'up' | 'down') => {
    const newSeps = [...separators]
    const target = direction === 'up' ? index - 1 : index + 1
    if (target < 0 || target >= newSeps.length) return
    ;[newSeps[index], newSeps[target]] = [newSeps[target], newSeps[index]]
    onChange(newSeps)
  }

  return (
    <div className="space-y-3">
      {/* 当前分隔符列表（按优先级排序） */}
      <div className="space-y-1.5">
        {separators.map((sep, i) => (
          <div
            key={i}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 group hover:border-indigo-300 transition-colors"
          >
            {/* 序号 */}
            <span className="text-xs font-medium text-gray-400 w-5 shrink-0">{i + 1}</span>
            {/* 分隔符名称 */}
            <span className="flex-1 text-sm text-gray-700 font-mono">
              {SEPARATOR_DISPLAY[sep] || JSON.stringify(sep)}
            </span>
            {/* 操作按钮 */}
            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => moveSeparator(i, 'up')}
                disabled={i === 0}
                className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-200 disabled:opacity-30 transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
              </button>
              <button
                onClick={() => moveSeparator(i, 'down')}
                disabled={i === separators.length - 1}
                className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-200 disabled:opacity-30 transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              <button
                onClick={() => removeSeparator(i)}
                className="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors ml-1"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* 添加新分隔符 */}
      <div className="flex gap-2">
        <select
          value=""
          onChange={(e) => {
            if (e.target.value) addSeparator(e.target.value)
          }}
          className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm
            focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
        >
          <option value="">添加分隔符…</option>
          {presets.filter(p => !separators.includes(p)).map(p => (
            <option key={p} value={p}>{SEPARATOR_DISPLAY[p] || JSON.stringify(p)}</option>
          ))}
        </select>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newSep}
            onChange={e => setNewSep(e.target.value)}
            placeholder="自定义…"
            maxLength={10}
            className="w-28 px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono
              focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
          />
          <button
            onClick={() => {
              if (newSep && !separators.includes(newSep)) {
                addSeparator(newSep)
              }
            }}
            disabled={!newSep || separators.includes(newSep)}
            className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium
              hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            添加
          </button>
        </div>
      </div>
    </div>
  )
}
