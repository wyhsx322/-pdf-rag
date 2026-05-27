import { useState, useEffect, useRef, useCallback } from 'react'
import type { KnowledgeBase, ChatMessage } from '../types'
import { listKBs, chatQA } from '../api/client'
import { useChatContext, type DisplayMessage } from '../context/ChatContext'
import ConversationSidebar from '../components/ConversationSidebar'
import { useStickyState } from '../hooks/useStickyState'

export default function ChatQA() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [selectedKbId, setSelectedKbId] = useStickyState<number | null>('chat:selectedKbId', null)
  const [input, setInput] = useStickyState('chat:input', '')
  const [useReranker, setUseReranker] = useStickyState('chat:useReranker', false)
  const [useRewrite, setUseRewrite] = useStickyState('chat:useRewrite', true)
  const [sidebarCollapsed, setSidebarCollapsed] = useStickyState('chat:sidebarCollapsed', false)

  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const {
    conversations,
    loadConversations,
    currentConvId,
    messages,
    loading,
    selectConversation,
    newConversation,
    deleteConversation,
    saveExchange,
    setMessages,
    setLoading,
  } = useChatContext()

  // 加载知识库列表
  useEffect(() => {
    listKBs().then(setKbs).catch(() => {})
  }, [])

  // 选择知识库时加载对话列表
  useEffect(() => {
    if (selectedKbId) {
      loadConversations(selectedKbId)
    }
  }, [selectedKbId, loadConversations])

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSend = async () => {
    if (!selectedKbId || !input.trim() || loading) return
    const question = input.trim()
    setInput('')

    // 添加用户消息
    const userMsg: DisplayMessage = { role: 'user', content: question, sources: [], figures: [], isStreaming: false }
    setMessages([...messages, userMsg])
    setLoading(true)

    // 构建历史记录（最近 10 轮）
    const history: ChatMessage[] = []
    const recent = messages.slice(-20)
    for (const msg of recent) {
      history.push({ role: msg.role, content: msg.content })
    }

    // 添加占位助手消息
    const assistantMsg: DisplayMessage = { role: 'assistant', content: '', sources: [], figures: [], isStreaming: true }
    setMessages([...messages, userMsg, assistantMsg])

    // 保存这些引用以便在回调中使用
    let fullContent = ''
    let allSources: string[] = []
    let allFigures: Array<{ chunk_id: string; source: string; image_file: string; caption: string; page: number | null; figure_type: string }> = []

    const controller = chatQA(
      selectedKbId,
      question,
      history,
      10,
      useReranker,
      useRewrite,
      (text) => {
        fullContent += text
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            last.content += text
          }
          return [...updated]
        })
      },
      (source) => {
        allSources.push(source)
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            last.sources = [...last.sources, source]
          }
          return [...updated]
        })
      },
      (finalAnswer, sources, figures) => {
        fullContent = finalAnswer || fullContent
        allSources = sources || allSources
        allFigures = figures || []
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            last.isStreaming = false
            last.content = fullContent
            last.sources = allSources
            last.figures = allFigures
          }
          return [...updated]
        })
        setLoading(false)
        // 持久化到后端
        saveExchange(selectedKbId!, question, fullContent, allSources)
      },
      (error) => {
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            last.content = last.content || `错误: ${error}`
            last.isStreaming = false
          }
          return [...updated]
        })
        setLoading(false)
      },
    )

    abortRef.current = controller
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleStop = () => {
    abortRef.current?.abort()
    setLoading(false)
    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.role === 'assistant' && last.isStreaming) {
        last.isStreaming = false
        if (!last.content) last.content = '(已停止生成)'
      }
      return [...updated]
    })
  }

  const handleClear = () => {
    if (messages.length > 0 && !confirm('确定要开始新对话吗？当前对话将自动保存。')) return
    newConversation()
  }

  const handleSelectConversation = (convId: number) => {
    if (loading) return
    selectConversation(convId)
  }

  const handleNewConversation = () => {
    if (loading) return
    newConversation()
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex">
      {/* 历史对话侧边栏 */}
      {selectedKbId && (
        <ConversationSidebar
          conversations={conversations}
          currentConvId={currentConvId}
          loading={loading}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onSelect={handleSelectConversation}
          onDelete={deleteConversation}
          onNew={handleNewConversation}
        />
      )}

      {/* 主聊天区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部标题栏 */}
        <div className="flex items-center justify-between mb-4 shrink-0">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">问答对话</h2>
            <p className="text-sm text-gray-500 mt-1">基于知识库的流式问答，多轮对话，自动引用来源</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={selectedKbId || ''}
              onChange={e => setSelectedKbId(Number(e.target.value) || null)}
              className="w-44 px-3.5 py-2 rounded-lg border border-gray-300 text-sm
                focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
            >
              <option value="">选择知识库…</option>
              {kbs.map(kb => (
                <option key={kb.id} value={kb.id}>{kb.name}</option>
              ))}
            </select>

            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-gray-500">
              <input
                type="checkbox"
                checked={useRewrite}
                onChange={e => setUseRewrite(e.target.checked)}
                className="w-3 h-3 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              改写
            </label>

            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-gray-500">
              <input
                type="checkbox"
                checked={useReranker}
                onChange={e => setUseReranker(e.target.checked)}
                className="w-3 h-3 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              Reranker
            </label>

            <button
              onClick={handleClear}
              disabled={loading}
              className="px-3 py-2 rounded-lg text-sm text-gray-500 border border-gray-200
                hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              新对话
            </button>
          </div>
        </div>

        {/* 聊天区域 */}
        <div className="flex-1 overflow-y-auto mb-4 space-y-4 min-h-0">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <span className="text-5xl mb-4 block">💬</span>
                <h3 className="text-lg font-medium text-gray-700 mb-2">开始论文问答</h3>
                <p className="text-sm text-gray-400 max-w-md">
                  选择知识库后，在下方输入你的问题。系统将基于论文内容回答，并自动标注引用来源。
                </p>
                <div className="mt-6 grid grid-cols-1 gap-2 max-w-xs mx-auto">
                  {[
                    '这篇论文的主要研究问题是什么？',
                    '研究方法使用了哪些数据？',
                    '请总结论文的核心发现和结论',
                  ].map((q, i) => (
                    <button
                      key={i}
                      onClick={() => { setInput(q); inputRef.current?.focus() }}
                      className="text-left px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-500
                        hover:border-indigo-300 hover:text-indigo-600 transition-colors truncate"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-1' : ''}`}>
                  <div className={`flex items-center gap-2 mb-1 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                    <span className="text-xs text-gray-400">
                      {msg.role === 'user' ? '你' : '论文助手'}
                    </span>
                  </div>

                  <div className={`rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-indigo-600 text-white rounded-br-md'
                      : 'bg-white border border-gray-200 text-gray-700 rounded-bl-md shadow-sm'
                  }`}>
                    <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                      {msg.content}
                      {msg.isStreaming && (
                        <span className="inline-block w-2 h-4 bg-indigo-600 ml-0.5 animate-pulse rounded-sm" />
                      )}
                    </div>

                    {!msg.isStreaming && msg.sources.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100">
                        <p className="text-xs font-medium text-gray-500 mb-2">📚 参考来源</p>
                        <div className="space-y-1.5">
                          {msg.sources.map((src, si) => (
                            <div
                              key={si}
                              className="text-xs text-gray-500 bg-gray-100 rounded-lg px-3 py-2 font-mono leading-relaxed"
                            >
                              {src}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {!msg.isStreaming && msg.figures.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100">
                        <p className="text-xs font-medium text-gray-500 mb-2">📷 相关图片</p>
                        <div className="flex flex-wrap gap-3">
                          {msg.figures.map((fig, fi) => (
                            <div key={fi} className="max-w-[250px]">
                              <img
                                src={`/api/images/${fig.source}/${fig.image_file}`}
                                alt={fig.caption || '论文图片'}
                                className="w-full rounded-lg border border-gray-200 object-contain"
                                loading="lazy"
                              />
                              {fig.caption && (
                                <p className="text-xs text-gray-500 mt-1 truncate">{fig.caption}</p>
                              )}
                              {fig.page && (
                                <p className="text-xs text-gray-400 mt-0.5">第 {fig.page} 页</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={chatEndRef} />
        </div>

        {/* 输入区域 */}
        <div className="shrink-0 bg-white rounded-xl border border-gray-200 shadow-sm p-4">
          <div className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedKbId ? '输入你的问题，按 Enter 发送…' : '请先选择知识库'}
              disabled={!selectedKbId}
              className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 text-sm
                focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none
                disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            />

            {loading ? (
              <button
                onClick={handleStop}
                className="px-5 py-2.5 rounded-lg bg-red-500 text-sm font-medium text-white
                  hover:bg-red-600 transition-colors shadow-sm"
              >
                停止
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!selectedKbId || !input.trim()}
                className="px-5 py-2.5 rounded-lg bg-indigo-600 text-sm font-medium text-white
                  hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
              >
                发送
              </button>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            按 Enter 发送，系统将严格依据论文内容回答，无法回答时会明确说明
          </p>
        </div>
      </div>
    </div>
  )
}
