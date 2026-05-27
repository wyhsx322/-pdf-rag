import { useState } from 'react'
import type { Document } from '../types'
import { DOC_STATUS_LABELS, DOC_STATUS_COLORS } from '../types'

interface DocumentRowProps {
  doc: Document
  onDelete: (id: number) => void
  onProcess: (id: number) => void
  onViewVectorStats: (id: number) => void
  onDeleteVectors: (id: number) => void
  onReindex: (id: number) => void
  processing: boolean
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function DocumentRow({ doc, onDelete, onProcess, onViewVectorStats, onDeleteVectors, onReindex, processing }: DocumentRowProps) {
  const isProcessing = processing || doc.status === 'parsed'
  const [showVectorMenu, setShowVectorMenu] = useState(false)

  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50/50 transition-colors">
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          <span className="text-red-500 shrink-0">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" />
            </svg>
          </span>
          <div>
            <p className={`text-sm font-medium truncate max-w-[250px] ${doc.status === 'indexed' ? 'text-emerald-600' : 'text-gray-900'}`} title={doc.original_name}>
              {doc.original_name}
            </p>
            <p className="text-xs text-gray-400">{formatFileSize(doc.file_size)}</p>
          </div>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${DOC_STATUS_COLORS[doc.status]}`}>
          {DOC_STATUS_LABELS[doc.status]}
        </span>
      </td>
      <td className="py-3 px-4 text-sm text-gray-500 text-center">
        {doc.page_count ? `${doc.page_count} 页` : '-'}
      </td>
      <td className="py-3 px-4 text-sm text-gray-400">
        {new Date(doc.created_at).toLocaleString('zh-CN')}
      </td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-1.5">
          {/* 处理按钮 */}
          {doc.status !== 'indexed' && (
            <button
              onClick={() => onProcess(doc.id)}
              disabled={isProcessing}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-indigo-600
                hover:bg-indigo-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              title="执行解析→切片→入库流水线"
            >
              {isProcessing ? '处理中…' : '处理'}
            </button>
          )}

          {/* 向量库操作下拉菜单 */}
          {(doc.status === 'indexed' || doc.status === 'chunked') && (
            <div className="relative">
              <button
                onClick={() => setShowVectorMenu(!showVectorMenu)}
                className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-500
                  hover:bg-slate-100 transition-colors"
                title="向量库操作"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                </svg>
              </button>
              {showVectorMenu && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowVectorMenu(false)} />
                  <div className="absolute right-0 top-full mt-1 z-20 w-36 bg-white rounded-lg shadow-lg border border-gray-200 py-1">
                    <button
                      onClick={() => { onViewVectorStats(doc.id); setShowVectorMenu(false) }}
                      className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
                    >
                      查看向量统计
                    </button>
                    {doc.status === 'indexed' && (
                      <button
                        onClick={() => { onDeleteVectors(doc.id); setShowVectorMenu(false) }}
                        className="w-full text-left px-3 py-2 text-xs text-amber-600 hover:bg-amber-50 transition-colors"
                      >
                        删除向量数据
                      </button>
                    )}
                    {doc.status === 'chunked' && (
                      <button
                        onClick={() => { onReindex(doc.id); setShowVectorMenu(false) }}
                        className="w-full text-left px-3 py-2 text-xs text-indigo-600 hover:bg-indigo-50 transition-colors"
                      >
                        重新索引
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* 删除按钮 */}
          <button
            onClick={() => onDelete(doc.id)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
            title="删除文档"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </td>
    </tr>
  )
}
