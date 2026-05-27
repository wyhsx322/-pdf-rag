import { useState } from 'react'
import type { KBType } from '../types'
import { KB_TYPE_LABELS, KB_TYPE_ICONS } from '../types'

interface CreateKBDialogProps {
  open: boolean
  onClose: () => void
  onCreate: (name: string, type: KBType, description: string) => void
  loading: boolean
}

export default function CreateKBDialog({ open, onClose, onCreate, loading }: CreateKBDialogProps) {
  const [name, setName] = useState('')
  const [type, setType] = useState<KBType>('study')
  const [description, setDescription] = useState('')

  if (!open) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    onCreate(name.trim(), type, description.trim())
    setName('')
    setDescription('')
    setType('study')
  }

  const types: KBType[] = ['work', 'study', 'personal']

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 遮罩 */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* 弹窗 */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 mx-4 animate-in">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-900">新建知识库</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {/* 名称 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">知识库名称</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="例如：机器学习论文"
              maxLength={50}
              className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 text-sm
                focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none
                transition-all duration-150 placeholder:text-gray-400"
              autoFocus
              required
            />
          </div>

          {/* 类型 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">知识库类型</label>
            <div className="grid grid-cols-3 gap-2">
              {types.map(t => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setType(t)}
                  className={`flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-lg border text-sm font-medium transition-all duration-150 ${
                    type === t
                      ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                      : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                  }`}
                >
                  <span>{KB_TYPE_ICONS[t]}</span>
                  {KB_TYPE_LABELS[t]}
                </button>
              ))}
            </div>
          </div>

          {/* 描述 */}
          <div className="mb-5">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">描述（可选）</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="简要描述这个知识库的用途…"
              maxLength={200}
              rows={3}
              className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 text-sm
                focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none
                transition-all duration-150 placeholder:text-gray-400 resize-none"
            />
          </div>

          {/* 按钮 */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-lg border border-gray-200 text-sm font-medium text-gray-600
                hover:bg-gray-50 transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={!name.trim() || loading}
              className="flex-1 py-2.5 rounded-lg bg-indigo-600 text-sm font-medium text-white
                hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '创建中…' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
