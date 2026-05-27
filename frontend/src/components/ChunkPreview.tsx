import type { ChunkResult } from '../types'

interface ChunkPreviewProps {
  chunks: ChunkResult[]
  totalChunks: number
  avgChunkSize: number
  loading: boolean
}

export default function ChunkPreview({ chunks, totalChunks, avgChunkSize, loading }: ChunkPreviewProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (chunks.length === 0) {
    return (
      <div className="text-center py-20">
        <span className="text-4xl mb-3 block">🔬</span>
        <p className="text-sm text-gray-400">配置左侧参数后，点击「预览切片」查看效果</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 统计信息 */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-indigo-50 rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-indigo-700">{totalChunks}</p>
          <p className="text-xs text-indigo-500 mt-1">总块数</p>
        </div>
        <div className="bg-emerald-50 rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-emerald-700">{avgChunkSize}</p>
          <p className="text-xs text-emerald-500 mt-1">平均字符数</p>
        </div>
        <div className="bg-amber-50 rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-amber-700">
            {chunks.filter(c => c.has_figure).length}
          </p>
          <p className="text-xs text-amber-500 mt-1">含图片块</p>
        </div>
      </div>

      {/* 切片列表 */}
      <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
        {chunks.map((chunk, i) => (
          <div
            key={chunk.chunk_id || i}
            className="bg-white rounded-lg border border-gray-200 p-4 hover:border-indigo-300 transition-colors"
          >
            {/* 块头部 */}
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-600 font-mono">
                {chunk.chunk_id || `#${i + 1}`}
              </span>
              {chunk.page > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 text-blue-600">
                  第 {chunk.page} 页
                </span>
              )}
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200">
                {chunk.text_length} 字符
              </span>
              {chunk.has_figure && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-600">
                  含图片
                </span>
              )}
            </div>

            {/* 文本内容 */}
            <div className="relative">
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-all">
                {chunk.text}
              </p>
              {chunk.text_length > 500 && (
                <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-white to-transparent pointer-events-none" />
              )}
            </div>

            {/* 截断提示 */}
            {chunk.text_length > 500 && (
              <p className="text-xs text-gray-400 mt-1">
                （预览显示前 500 字符，完整内容共 {chunk.text_length} 字符）
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
