import { useState, useEffect, useRef, useCallback } from 'react'
import { Send, Square, Quote, X, BookOpen, Image as ImageIcon, Sparkles, Brain, Check, Ban } from 'lucide-react'
import { toast } from 'sonner'
import type { KnowledgeBase } from '../../entities/knowledge-base/model'
import type { ChatMessage } from '../../entities/chat/model'
import {
  chatQA,
  approveLongTermMemoryCandidate,
  rejectLongTermMemoryCandidate,
  type LongTermMemoryCandidate,
  type LongTermMemoryUsed,
} from '../../features/chat-session/api'
import { listKBs } from '../../entities/knowledge-base/api'
import { useChatContext, type DisplayMessage } from '../../features/chat-session/ChatContext'
import { useAppStore } from '../../shared/state/useAppStore'
import Markdown from '../../shared/components/Markdown'
import { Select, Switch } from '../../shared/ui'
import { cn } from '../../shared/lib/cn'

const SUGGESTIONS = [
  '这篇论文的主要研究问题是什么？',
  '研究方法使用了哪些数据与模型？',
  '请总结论文的核心发现与结论',
  '论文存在哪些局限与未来工作？',
]

export default function Chat() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [input, setInput] = useState('')
  const [citationIdx, setCitationIdx] = useState<number | null>(null)

  const selectedKbId = useAppStore(s => s.selectedKbId)
  const setSelectedKbId = useAppStore(s => s.setSelectedKbId)
  const useRewrite = useAppStore(s => s.chatRewrite)
  const useReranker = useAppStore(s => s.chatReranker)
  const setChatRewrite = useAppStore(s => s.setChatRewrite)
  const setChatReranker = useAppStore(s => s.setChatReranker)

  const scrollRef = useRef<HTMLDivElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const {
    loadConversations, currentConvId, messages, loading,
    saveExchange, setMessages, setLoading,
  } = useChatContext()

  useEffect(() => { listKBs().then(setKbs).catch(() => {}) }, [])
  useEffect(() => { if (selectedKbId) loadConversations(selectedKbId) }, [selectedKbId, loadConversations])

  const scrollToBottom = useCallback(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [])
  useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

  // textarea 自适应高度
  const autoGrow = () => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }
  useEffect(autoGrow, [input])

  const handleSend = () => {
    if (!input.trim() || loading) return
    if (!selectedKbId) { toast.warning('请先选择知识库'); return }
    const question = input.trim()
    setInput('')

    const userMsg: DisplayMessage = { role: 'user', content: question, sources: [], figures: [], memoryUsed: [], memoryCandidate: null, isStreaming: false }
    const assistantMsg: DisplayMessage = { role: 'assistant', content: '', sources: [], figures: [], memoryUsed: [], memoryCandidate: null, isStreaming: true }
    const base = [...messages, userMsg]
    setMessages([...base, assistantMsg])
    setLoading(true)

    const history: ChatMessage[] = messages.slice(-20).map(m => ({ role: m.role, content: m.content }))

    let fullContent = ''
    let allSources: string[] = []
    let allFigures: DisplayMessage['figures'] = []
    let usedMemories: LongTermMemoryUsed[] = []
    let pendingMemory: LongTermMemoryCandidate | null = null

    const patchLast = (fn: (m: DisplayMessage) => void) => {
      setMessages(prev => {
        const u = [...prev]
        const last = u[u.length - 1]
        if (last && last.role === 'assistant') fn(last)
        return u
      })
    }

    abortRef.current = chatQA(
      selectedKbId, question, history, 10, useReranker, useRewrite, currentConvId,
      (text) => { fullContent += text; patchLast(m => { m.content += text }) },
      (source) => { allSources.push(source); patchLast(m => { m.sources = [...m.sources, source] }) },
      (finalAnswer, sources, figures, memoryUsed, memoryCandidate) => {
        fullContent = finalAnswer || fullContent
        allSources = sources || allSources
        allFigures = figures || []
        usedMemories = memoryUsed || usedMemories
        pendingMemory = memoryCandidate || pendingMemory
        patchLast(m => {
          m.isStreaming = false
          m.content = fullContent
          m.sources = allSources
          m.figures = allFigures
          m.memoryUsed = usedMemories
          m.memoryCandidate = pendingMemory
        })
        setLoading(false)
        saveExchange(selectedKbId, question, fullContent, allSources)
      },
      (error) => {
        patchLast(m => { m.content = m.content || `**出错了**：${error}`; m.isStreaming = false })
        setLoading(false)
        toast.error(error)
      },
      (candidate) => {
        pendingMemory = candidate
        patchLast(m => { m.memoryCandidate = candidate })
        toast.info('发现一条待确认的长期记忆')
      },
      (memories) => {
        usedMemories = memories
        patchLast(m => { m.memoryUsed = memories })
      },
      () => {
        toast.info('历史对话较长，已压缩早期上下文')
      },
    )
  }

  const handleApproveMemory = async (index: number, candidateId: number) => {
    try {
      const updated = await approveLongTermMemoryCandidate(candidateId)
      setMessages(prev => {
        const next = [...prev]
        const msg = next[index]
        if (msg?.memoryCandidate?.id === candidateId) {
          msg.memoryCandidate = updated
        }
        return next
      })
      toast.success('长期记忆已保存')
    } catch {
      toast.error('保存长期记忆失败')
    }
  }

  const handleRejectMemory = async (index: number, candidateId: number) => {
    try {
      const updated = await rejectLongTermMemoryCandidate(candidateId)
      setMessages(prev => {
        const next = [...prev]
        const msg = next[index]
        if (msg?.memoryCandidate?.id === candidateId) {
          msg.memoryCandidate = updated
        }
        return next
      })
      toast.success('已忽略这条长期记忆')
    } catch {
      toast.error('更新长期记忆失败')
    }
  }

  const handleStop = () => {
    abortRef.current?.abort()
    setLoading(false)
    setMessages(prev => {
      const u = [...prev]
      const last = u[u.length - 1]
      if (last?.role === 'assistant' && last.isStreaming) {
        last.isStreaming = false
        if (!last.content) last.content = '_（已停止生成）_'
      }
      return u
    })
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const kbOptions = kbs.map(kb => ({ value: String(kb.id), label: kb.name }))
  const isEmpty = messages.length === 0
  const citationMsg = citationIdx != null ? messages[citationIdx] : null

  // ── 输入框（空态居中 / 会话态底部共用） ──
  const inputBar = (
    <div className="rounded-3xl border border-white/80 bg-white/85 p-3 shadow-[0_18px_60px_rgba(15,23,42,0.09)] backdrop-blur transition-shadow focus-within:shadow-glow">
      <textarea
        ref={taRef}
        rows={1}
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={selectedKbId ? '输入你的问题，Enter 发送，Shift+Enter 换行…' : '请先在上方选择知识库…'}
        className="max-h-[220px] w-full resize-none bg-transparent px-3 py-2.5 text-sm leading-6 text-slate-800 outline-none placeholder:text-slate-400"
      />
      <div className="flex items-center justify-between px-1.5 pb-0.5">
        <span className="text-xs text-slate-400">严格依据知识库内容回答，并标注引用来源</span>
        {loading ? (
          <button onClick={handleStop} className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-500 text-white transition-colors hover:bg-rose-600">
            <Square className="h-4 w-4" fill="currentColor" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-950 text-white shadow-soft transition-all hover:bg-indigo-600 hover:shadow-glow disabled:opacity-40 disabled:shadow-none"
          >
            <Send className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  )

  return (
    <div className="flex h-full min-h-0">
      {/* 主聊天区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 顶部工具条 */}
        <div className="flex h-16 shrink-0 items-center gap-4 border-b border-white/70 bg-white/70 px-8 backdrop-blur">
          <Select
            value={selectedKbId ? String(selectedKbId) : ''}
            onValueChange={v => setSelectedKbId(Number(v) || null)}
            options={kbOptions}
            placeholder="选择知识库…"
            className="h-9 w-52"
          />
          <div className="flex-1" />
          <Switch checked={useRewrite} onCheckedChange={setChatRewrite} label="查询改写" />
          <Switch checked={useReranker} onCheckedChange={setChatReranker} label="重排序" />
        </div>

        {isEmpty ? (
          /* 空态 hero */
          <div className="flex flex-1 flex-col items-center justify-center px-8">
            <div className="w-full max-w-3xl text-center">
              <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-950 shadow-glow">
                <Sparkles className="h-7 w-7 text-white" />
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-950">今天想研究什么？</h1>
              <p className="mt-3 text-sm text-slate-500">
                选择知识库后提问，多智能体将基于论文内容作答并回链引用来源
              </p>
              <div className="mt-8">{inputBar}</div>
              <div className="mt-5 flex flex-wrap justify-center gap-2.5">
                {SUGGESTIONS.map(q => (
                  <button
                    key={q}
                    onClick={() => { setInput(q); taRef.current?.focus() }}
                    className="rounded-full border border-white/80 bg-white/70 px-4 py-2 text-xs text-slate-500 shadow-soft transition-colors hover:border-indigo-300 hover:text-indigo-600"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* 消息流 */}
            <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
              <div className="mx-auto max-w-4xl space-y-7 px-8 py-10">
                {messages.map((msg, i) => (
                  <MessageRow
                    key={i}
                    msg={msg}
                    onOpenCitations={() => setCitationIdx(i)}
                    onApproveMemory={() => msg.memoryCandidate && handleApproveMemory(i, msg.memoryCandidate.id)}
                    onRejectMemory={() => msg.memoryCandidate && handleRejectMemory(i, msg.memoryCandidate.id)}
                    active={citationIdx === i}
                  />
                ))}
              </div>
            </div>
            {/* 底部输入 */}
            <div className="shrink-0 px-8 pb-6">
              <div className="mx-auto max-w-4xl">{inputBar}</div>
            </div>
          </>
        )}
      </div>

      {/* 右侧引用面板 */}
      {citationMsg && (
        <CitationPanel msg={citationMsg} onClose={() => setCitationIdx(null)} />
      )}
    </div>
  )
}

// ── 单条消息 ──
function MessageRow({
  msg,
  onOpenCitations,
  onApproveMemory,
  onRejectMemory,
  active,
}: {
  msg: DisplayMessage
  onOpenCitations: () => void
  onApproveMemory: () => void
  onRejectMemory: () => void
  active: boolean
}) {
  if (msg.role === 'user') {
    return (
      <div className="flex animate-fade-in justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-gradient-to-r from-indigo-500 to-violet-500 px-4 py-2.5 text-sm leading-relaxed text-white shadow-soft">
          {msg.content}
        </div>
      </div>
    )
  }

  const citationCount = msg.sources.length + msg.figures.length

  return (
    <div className="flex animate-fade-in gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500">
        <Sparkles className="h-4 w-4 text-white" />
      </div>
      <div className="min-w-0 flex-1 pt-0.5">
        {msg.content ? (
          <Markdown content={msg.content} />
        ) : (
          msg.isStreaming && <span className="text-sm text-slate-400">思考中…</span>
        )}
        {msg.isStreaming && msg.content && (
          <span className="ml-0.5 inline-block h-4 w-1.5 animate-blink rounded-sm bg-indigo-500 align-middle" />
        )}
        {!msg.isStreaming && citationCount > 0 && (
          <button
            onClick={onOpenCitations}
            className={cn(
              'mt-3 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              active
                ? 'border-indigo-300 bg-indigo-50 text-indigo-600'
                : 'border-slate-200 text-slate-500 hover:border-indigo-300 hover:text-indigo-600',
            )}
          >
            <Quote className="h-3.5 w-3.5" />
            引用来源 {citationCount}
          </button>
        )}
        {!msg.isStreaming && msg.memoryUsed && msg.memoryUsed.length > 0 && (
          <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-slate-700">
              <Brain className="h-3.5 w-3.5 text-indigo-500" />
              本次使用长期记忆 {msg.memoryUsed.length}
            </summary>
            <div className="mt-2 space-y-2">
              {msg.memoryUsed.map(memory => (
                <div key={memory.id} className="rounded-md bg-white p-2">
                  <div className="mb-1 text-[11px] text-slate-400">#{memory.id} · {memory.category} · score {memory.score.toFixed(2)}</div>
                  <div className="whitespace-pre-wrap break-words">{memory.content}</div>
                </div>
              ))}
            </div>
          </details>
        )}
        {!msg.isStreaming && msg.memoryCandidate && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            <div className="mb-1.5 flex items-center gap-1.5 font-medium">
              <Brain className="h-3.5 w-3.5" />
              待确认长期记忆
              {msg.memoryCandidate.status !== 'pending' && (
                <span className="rounded bg-white/70 px-1.5 py-0.5 text-[11px]">{msg.memoryCandidate.status}</span>
              )}
            </div>
            <div className="whitespace-pre-wrap break-words rounded-md bg-white/70 p-2">{msg.memoryCandidate.content}</div>
            {msg.memoryCandidate.status === 'pending' && (
              <div className="mt-2 flex gap-2">
                <button
                  onClick={onApproveMemory}
                  className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2 py-1 text-white hover:bg-emerald-700"
                >
                  <Check className="h-3.5 w-3.5" />
                  保存
                </button>
                <button
                  onClick={onRejectMemory}
                  className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-white px-2 py-1 text-amber-900 hover:bg-amber-100"
                >
                  <Ban className="h-3.5 w-3.5" />
                  忽略
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── 右侧引用面板 ──
function CitationPanel({ msg, onClose }: { msg: DisplayMessage; onClose: () => void }) {
  return (
    <div className="flex w-[360px] shrink-0 animate-slide-in-right flex-col border-l border-slate-200 bg-white">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 px-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
          <BookOpen className="h-4 w-4 text-indigo-500" />
          引用来源
        </div>
        <button onClick={onClose} className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {msg.sources.map((src, i) => (
          <div key={i} className="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-indigo-600">
              <span className="flex h-4 w-4 items-center justify-center rounded bg-indigo-100 text-[10px]">{i + 1}</span>
              文本片段
            </div>
            <p className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-slate-600">{src}</p>
          </div>
        ))}
        {msg.figures.map((fig, i) => (
          <div key={i} className="rounded-xl border border-slate-200 p-3">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-violet-600">
              <ImageIcon className="h-3.5 w-3.5" />
              相关图片{fig.page ? ` · 第 ${fig.page} 页` : ''}
            </div>
            <img
              src={`/api/images/${fig.source}/${fig.image_file}`}
              alt={fig.caption || '论文图片'}
              className="w-full rounded-lg border border-slate-200 object-contain"
              loading="lazy"
            />
            {fig.caption && <p className="mt-1.5 text-xs text-slate-500">{fig.caption}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
