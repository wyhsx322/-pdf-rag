import { useState, useEffect, useRef } from 'react'
import type { KnowledgeBase, SearchResultItem } from '../types'
import { listKBs, hybridSearch } from '../api/client'
import type { SearchResponse } from '../api/client'
import { useStickyState } from '../hooks/useStickyState'

export default function HybridSearch() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [selectedKbId, setSelectedKbId] = useStickyState<number | null>('search:selectedKbId', null)
  const [query, setQuery] = useStickyState('search:query', '')
  const [topK, setTopK] = useStickyState('search:topK', 10)
  const [useReranker, setUseReranker] = useStickyState('search:useReranker', false)
  const [useRewrite, setUseRewrite] = useStickyState('search:useRewrite', true)
  const [useHyde, setUseHyde] = useStickyState('search:useHyde', false)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useStickyState<SearchResultItem[]>('search:results', [])
  const [searchMode, setSearchMode] = useStickyState('search:searchMode', '')
  const [totalResults, setTotalResults] = useStickyState('search:totalResults', 0)
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listKBs().then(setKbs).catch(() => {})
  }, [])

  const handleSearch = async () => {
    if (!selectedKbId || !query.trim()) return
    setLoading(true)
    setExpandedIdx(null)
    try {
      const data: SearchResponse = await hybridSearch(
        selectedKbId,
        query.trim(),
        topK,
        useReranker,
        useRewrite,
        useHyde,
      )
      setResults(data.results)
      setSearchMode(data.search_mode)
      setTotalResults(data.total_results)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '检索失败，请检查后端服务')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  const highlightQuery = (text: string, q: string) => {
    if (!q.trim()) return text
    const words = q.split(/\s+/).filter(w => w.length > 0)
    let result = text
    for (const word of words) {
      const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const regex = new RegExp(`(${escaped})`, 'gi')
      result = result.replace(regex, '<mark class="bg-amber-200 rounded px-0.5">$1</mark>')
    }
    return result
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">混合检索</h2>
        <p className="text-sm text-gray-500 mt-1">向量语义 + BM25 关键词匹配，RRF 融合与可选 Reranker 重排序</p>
      </div>

      {/* 搜索栏 */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-6">
        {/* 第一行：知识库选择 + 搜索框 */}
        <div className="flex gap-3 mb-4">
          <select
            value={selectedKbId || ''}
            onChange={e => setSelectedKbId(Number(e.target.value) || null)}
            className="w-48 px-3.5 py-2.5 rounded-lg border border-gray-300 text-sm
              focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
          >
            <option value="">选择知识库…</option>
            {kbs.map(kb => (
              <option key={kb.id} value={kb.id}>{kb.name}</option>
            ))}
          </select>

          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入查询词，测试检索召回效果…"
              className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-300 text-sm
                focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
            />
            <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          <button
            onClick={handleSearch}
            disabled={loading || !selectedKbId || !query.trim()}
            className="px-6 py-2.5 rounded-lg bg-indigo-600 text-sm font-medium text-white
              hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {loading ? '检索中…' : '检索'}
          </button>
        </div>

        {/* 第二行：高级选项 */}
        <div className="flex items-center gap-6 flex-wrap">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">返回数量</label>
            <select
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 outline-none"
            >
              {[5, 10, 15, 20, 30].map(n => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={useRewrite}
              onChange={e => setUseRewrite(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span className="text-xs text-gray-600">查询改写</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={useHyde}
              onChange={e => setUseHyde(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span className="text-xs text-gray-600">HyDE 增强</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={useReranker}
              onChange={e => setUseReranker(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span className="text-xs text-gray-600">BGE-Reranker 重排序</span>
          </label>
        </div>
      </div>

      {/* 检索模式提示 */}
      {searchMode && (
        <div className="mb-4 flex items-center gap-2 text-xs text-gray-500">
          <span>检索策略：</span>
          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-600 font-medium">{searchMode}</span>
          <span>· 共 {totalResults} 条结果</span>
        </div>
      )}

      {/* 结果列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-3">
          {results.map((item, idx) => (
            <div
              key={item.chunk_id}
              className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden hover:border-indigo-300 transition-colors"
            >
              {/* 头部信息 */}
              <div className="px-5 py-3 bg-gray-50/50 border-b border-gray-100 flex items-center gap-3 flex-wrap">
                <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold bg-indigo-100 text-indigo-700">
                  #{item.rank}
                </span>
                <span className="text-xs text-gray-500 font-mono">{item.chunk_id}</span>
                <span className="text-xs text-gray-400">|</span>
                <span className="text-xs text-gray-500">来源: {item.source}.pdf</span>
                {item.page && (
                  <>
                    <span className="text-xs text-gray-400">|</span>
                    <span className="text-xs text-gray-500">第 {item.page} 页</span>
                  </>
                )}
                {item.is_figure && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs bg-amber-50 text-amber-600">
                    图片
                    {item.figure_type && ` · ${item.figure_type}`}
                  </span>
                )}

                <div className="flex-1" />

                {/* 分数详情 */}
                <div className="flex items-center gap-3 text-xs">
                  <span title="向量相似度" className="text-blue-600">
                    向量: {item.vector_score.toFixed(4)}
                  </span>
                  <span title="BM25 关键词得分" className="text-emerald-600">
                    BM25: {item.bm25_score.toFixed(4)}
                  </span>
                  <span title="RRF 融合得分" className="text-purple-600 font-medium">
                    RRF: {item.rrf_score.toFixed(4)}
                  </span>
                  {item.rerank_score != null && (
                    <span title="BGE-Reranker 精排得分" className="text-amber-600 font-semibold">
                      Rerank: {item.rerank_score.toFixed(4)}
                    </span>
                  )}
                </div>
              </div>

              {/* 文本内容 */}
              <div className="px-5 py-3">
                <p
                  className={`text-sm text-gray-700 leading-relaxed whitespace-pre-wrap ${expandedIdx !== idx ? 'line-clamp-4' : ''}`}
                  dangerouslySetInnerHTML={{
                    __html: expandedIdx === idx
                      ? highlightQuery(item.text, query)
                      : highlightQuery(item.text.slice(0, 400), query),
                  }}
                />
                {item.text.length > 400 && (
                  <button
                    onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                    className="mt-1 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                  >
                    {expandedIdx === idx ? '收起' : `展开全文 (${item.text.length} 字符)`}
                  </button>
                )}
                {/* 图片缩略图 */}
                {item.is_figure && item.image_file && (
                  <div className="mt-3 flex gap-3 items-start">
                    <img
                      src={`/api/images/${item.source}/${item.image_file}`}
                      alt={item.caption || '论文图片'}
                      className="max-w-[300px] max-h-[200px] rounded-lg border border-gray-200 object-contain"
                      loading="lazy"
                    />
                    <div className="text-xs text-gray-500 space-y-0.5">
                      {item.caption && <p className="font-medium text-gray-600">{item.caption}</p>}
                      {item.figure_type && <p>类型: {item.figure_type}</p>}
                      {item.page && <p>第 {item.page} 页</p>}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : query && !loading ? (
        <div className="text-center py-20">
          <span className="text-4xl mb-3 block">🔍</span>
          <p className="text-sm text-gray-400">未找到相关结果，请尝试其他关键词或确认知识库中有已入库文档</p>
        </div>
      ) : (
        <div className="text-center py-20">
          <span className="text-4xl mb-3 block">🔬</span>
          <p className="text-sm text-gray-400">选择知识库并输入查询词，测试混合检索的召回效果</p>
        </div>
      )}
    </div>
  )
}
