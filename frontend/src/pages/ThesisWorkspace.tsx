import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ── 类型 ──────────────────────────────────────────────────────────────────────

interface OutlineSection {
  id: string
  title: string
  key_points: string[]
  estimated_words: number
}

interface Outline {
  title: string
  abstract_hint: string
  research_gap: string
  sections: OutlineSection[]
}

interface ReviewResult {
  logic_score: number
  academic_tone: number
  citation_coverage: number
  argument_support: number
  overall_score: number
  strengths: string[]
  suggestions: string[]
  rewrite_needed: boolean
}

interface SectionDraft {
  content: string
  citations: string[]
  word_count: number
  status: 'draft'
  review?: ReviewResult
}

interface TraceEvent {
  agent_name: string
  action_type: string
  content: string
  tool_name?: string | null
  latency_ms?: number | null
  timestamp: string
}

interface Project {
  id: number
  title: string
  topic: string
  kb_id: number | null
  outline_status: string
  outline: Outline | null
  literature_notes: Record<string, unknown> | null
  sections_content: Record<string, SectionDraft> | null
}

// ── Trace 样式 ────────────────────────────────────────────────────────────────

const ACTION_STYLE: Record<string, { icon: string; cls: string; label: string }> = {
  start:       { icon: '▶', cls: 'text-indigo-400', label: '启动' },
  think:       { icon: '💭', cls: 'text-slate-400', label: '推理' },
  tool_call:   { icon: '🔧', cls: 'text-amber-400', label: '工具调用' },
  tool_result: { icon: '✓',  cls: 'text-emerald-400', label: '工具结果' },
  output:      { icon: '📄', cls: 'text-blue-400', label: '输出' },
  error:       { icon: '✕',  cls: 'text-red-400', label: '错误' },
}

function TraceItem({ ev }: { ev: TraceEvent }) {
  const s = ACTION_STYLE[ev.action_type] ?? { icon: '·', cls: 'text-slate-500', label: ev.action_type }
  return (
    <div className="flex gap-3 py-2 border-b border-slate-700/50 last:border-0">
      <span className={`text-sm mt-0.5 shrink-0 ${s.cls}`}>{s.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-medium text-slate-300">{ev.agent_name}</span>
          <span className="text-xs text-slate-600">·</span>
          <span className={`text-xs ${s.cls}`}>{s.label}</span>
          {ev.tool_name && (
            <span className="text-xs bg-amber-500/10 text-amber-400 px-1.5 rounded">{ev.tool_name}</span>
          )}
          {ev.latency_ms != null && (
            <span className="text-xs text-slate-600 ml-auto">{ev.latency_ms}ms</span>
          )}
        </div>
        <p className="text-xs text-slate-400 line-clamp-2">{ev.content}</p>
      </div>
    </div>
  )
}

// ── 大纲视图 ──────────────────────────────────────────────────────────────────

function OutlineView({
  outline,
  status,
  onConfirm,
}: {
  outline: Outline
  status: string
  onConfirm: (o: Outline) => void
}) {
  const [edited, setEdited] = useState<Outline>(outline)
  const totalWords = edited.sections.reduce((s, sec) => s + sec.estimated_words, 0)

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{edited.title}</h3>
          <p className="text-xs text-slate-400 mt-1">{edited.abstract_hint}</p>
        </div>
        <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-medium ${
          status === 'confirmed'
            ? 'bg-emerald-500/20 text-emerald-300'
            : 'bg-amber-500/20 text-amber-300'
        }`}>
          {status === 'confirmed' ? '已确认' : '待确认'}
        </span>
      </div>

      <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-lg px-4 py-3">
        <p className="text-xs text-indigo-300 font-medium mb-1">研究空白 / 创新点</p>
        <p className="text-sm text-slate-300">{edited.research_gap}</p>
      </div>

      <div className="space-y-2">
        {edited.sections.map((sec, idx) => (
          <div key={sec.id} className="bg-slate-800/60 border border-slate-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-200">
                {idx + 1}. {sec.title}
              </span>
              <span className="text-xs text-slate-500">{sec.estimated_words.toLocaleString()} 字</span>
            </div>
            <ul className="space-y-1">
              {sec.key_points.map((kp, ki) => (
                <li key={ki} className="text-xs text-slate-400 flex gap-2">
                  <span className="text-slate-600 shrink-0">·</span>{kp}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs text-slate-500">预计总字数：{totalWords.toLocaleString()} 字</span>
        {status !== 'confirmed' ? (
          <button
            onClick={() => onConfirm(edited)}
            className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-white rounded-lg text-sm font-medium transition-colors"
          >
            确认大纲
          </button>
        ) : (
          <span className="text-xs text-emerald-400 font-medium">大纲已确认，可前往写作工坊</span>
        )}
      </div>
    </div>
  )
}

// ── 评审卡片 ──────────────────────────────────────────────────────────────────

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round((score / 5) * 100)
  const color = score >= 4 ? 'bg-emerald-500' : score >= 3 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-400 w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-400 w-8 text-right">{score.toFixed(1)}</span>
    </div>
  )
}

function ReviewCard({
  review,
  hitlPending,
  onRewrite,
  onDismiss,
}: {
  review: ReviewResult
  hitlPending: boolean
  onRewrite: () => void
  onDismiss: () => void
}) {
  const overall = review.overall_score
  const overallColor = overall >= 4 ? 'text-emerald-400' : overall >= 3 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className={`border rounded-lg p-3 space-y-3 ${
      hitlPending ? 'border-amber-500/40 bg-amber-500/5' : 'border-slate-600/50 bg-slate-900/40'
    }`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-300">学术评审结果</span>
        <span className={`text-sm font-bold ${overallColor}`}>
          {overall.toFixed(1)}<span className="text-xs font-normal text-slate-500">/5.0</span>
        </span>
      </div>

      <div className="space-y-1.5">
        <ScoreBar label="逻辑严密性" score={review.logic_score} />
        <ScoreBar label="学术规范性" score={review.academic_tone} />
        <ScoreBar label="引用充分度" score={review.citation_coverage} />
        <ScoreBar label="论点支撑度" score={review.argument_support} />
      </div>

      {review.suggestions.length > 0 && (
        <div>
          <p className="text-xs text-slate-500 mb-1">改进建议：</p>
          <ul className="space-y-0.5">
            {review.suggestions.map((s, i) => (
              <li key={i} className="text-xs text-slate-400 flex gap-1.5">
                <span className="text-amber-500 shrink-0">·</span>{s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {hitlPending && (
        <div className="pt-1 border-t border-amber-500/20">
          <p className="text-xs text-amber-400 mb-2">综合评分偏低，建议重新写作：</p>
          <div className="flex gap-2">
            <button
              onClick={onRewrite}
              className="px-3 py-1.5 bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg text-xs font-medium transition-colors"
            >
              接受建议，重新写作
            </button>
            <button
              onClick={onDismiss}
              className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs transition-colors"
            >
              忽略，保留草稿
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── 写作工坊 ──────────────────────────────────────────────────────────────────

function SectionCard({
  section,
  idx,
  draft,
  isWriting,
  isReviewing,
  hitlPending,
  onWrite,
  onReview,
  onDismissHitl,
}: {
  section: OutlineSection
  idx: number
  draft: SectionDraft | undefined
  isWriting: boolean
  isReviewing: boolean
  hitlPending: boolean
  onWrite: (section: OutlineSection) => void
  onReview: (section: OutlineSection) => void
  onDismissHitl: (sectionId: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const isActive = isWriting || isReviewing

  return (
    <div className={`border rounded-xl transition-colors ${
      isWriting
        ? 'border-indigo-500/50 bg-indigo-500/5'
        : isReviewing
        ? 'border-purple-500/50 bg-purple-500/5'
        : 'border-slate-700/50 bg-slate-800/50 hover:border-slate-600/60'
    }`}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono text-slate-500 shrink-0">§{idx + 1}</span>
              <h4 className="text-sm font-medium text-slate-200 truncate">{section.title}</h4>
              {draft && (
                <span className="shrink-0 px-1.5 py-0.5 bg-emerald-500/20 text-emerald-300 rounded text-xs">
                  草稿 {draft.word_count}字
                </span>
              )}
              {draft?.review && (
                <span className={`shrink-0 px-1.5 py-0.5 rounded text-xs ${
                  draft.review.overall_score >= 4 ? 'bg-emerald-500/20 text-emerald-300' :
                  draft.review.overall_score >= 3 ? 'bg-amber-500/20 text-amber-300' :
                  'bg-red-500/20 text-red-300'
                }`}>
                  评分 {draft.review.overall_score.toFixed(1)}
                </span>
              )}
              {isWriting && (
                <span className="shrink-0 flex items-center gap-1 text-xs text-indigo-400">
                  <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse" />写作中
                </span>
              )}
              {isReviewing && (
                <span className="shrink-0 flex items-center gap-1 text-xs text-purple-400">
                  <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" />评审中
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-1">
              {section.key_points.slice(0, 3).map((kp, i) => (
                <span key={i} className="text-xs text-slate-500 bg-slate-700/30 px-1.5 py-0.5 rounded">
                  {kp.length > 20 ? kp.slice(0, 20) + '…' : kp}
                </span>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-slate-600">{section.estimated_words.toLocaleString()}字</span>
            {draft && (
              <button
                onClick={() => setExpanded(v => !v)}
                className="px-2.5 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs transition-colors"
              >
                {expanded ? '收起' : '查看'}
              </button>
            )}
            {draft && (
              <button
                onClick={() => onReview(section)}
                disabled={isActive}
                className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  isActive ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                  : 'bg-purple-500/20 hover:bg-purple-500/30 text-purple-300'
                }`}
              >
                {isReviewing ? '评审中...' : '评审'}
              </button>
            )}
            <button
              onClick={() => onWrite(section)}
              disabled={isActive}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                  : draft
                  ? 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                  : 'bg-indigo-500 hover:bg-indigo-400 text-white'
              }`}
            >
              {isWriting ? '写作中...' : draft ? '重新写作' : '开始写作'}
            </button>
          </div>
        </div>
      </div>

      {/* 草稿内容展开 */}
      {expanded && draft && (
        <div className="border-t border-slate-700/50 px-4 py-3 space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">共 {draft.word_count} 字</span>
            {draft.citations.length > 0 && (
              <span className="text-xs text-slate-500">· {draft.citations.length} 处引用</span>
            )}
          </div>
          <div className="bg-slate-900/60 rounded-lg p-3 max-h-64 overflow-y-auto">
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
              {draft.content}
            </pre>
          </div>
          {draft.citations.length > 0 && (
            <div className="space-y-0.5">
              <p className="text-xs text-slate-500 font-medium">引用来源：</p>
              {draft.citations.map((c, i) => (
                <p key={i} className="text-xs text-slate-500 pl-2">· {c}</p>
              ))}
            </div>
          )}
          {/* 评审结果 */}
          {draft.review && (
            <ReviewCard
              review={draft.review}
              hitlPending={hitlPending}
              onRewrite={() => { onWrite(section); onDismissHitl(section.id) }}
              onDismiss={() => onDismissHitl(section.id)}
            />
          )}
        </div>
      )}
    </div>
  )
}

function WritingView({
  outline,
  sectionsContent,
  writingSection,
  writingRunning,
  reviewingSection,
  reviewRunning,
  hitlSections,
  onWrite,
  onReview,
  onDismissHitl,
}: {
  outline: Outline
  sectionsContent: Record<string, SectionDraft>
  writingSection: string | null
  writingRunning: boolean
  reviewingSection: string | null
  reviewRunning: boolean
  hitlSections: Set<string>
  onWrite: (section: OutlineSection) => void
  onReview: (section: OutlineSection) => void
  onDismissHitl: (sectionId: string) => void
}) {
  const draftCount = Object.keys(sectionsContent).length
  const totalWritten = Object.values(sectionsContent).reduce((s, d) => s + d.word_count, 0)
  const reviewedCount = Object.values(sectionsContent).filter(d => d.review).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">章节写作工坊</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            草稿 {draftCount}/{outline.sections.length} 章节
            {draftCount > 0 && `，共 ${totalWritten.toLocaleString()} 字`}
            {reviewedCount > 0 && `，已评审 ${reviewedCount} 章`}
          </p>
        </div>
        <div className="flex gap-1.5 flex-wrap justify-end">
          {['ReAct Pattern', 'Tool Use', 'LLM-as-Judge', 'Long-term Memory'].map(tag => (
            <span key={tag} className="px-2 py-0.5 bg-slate-700/50 text-slate-500 rounded text-xs">
              {tag}
            </span>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {outline.sections.map((sec, idx) => (
          <SectionCard
            key={sec.id}
            section={sec}
            idx={idx}
            draft={sectionsContent[sec.id]}
            isWriting={writingSection === sec.id && writingRunning}
            isReviewing={reviewingSection === sec.id && reviewRunning}
            hitlPending={hitlSections.has(sec.id)}
            onWrite={onWrite}
            onReview={onReview}
            onDismissHitl={onDismissHitl}
          />
        ))}
      </div>
    </div>
  )
}

// ── 主页面 ─────────────────────────────────────────────────────────────────────

export default function ThesisWorkspace() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const projectId = Number(id)

  const [project, setProject] = useState<Project | null>(null)
  const [traces, setTraces] = useState<TraceEvent[]>([])
  const [running, setRunning] = useState(false)
  const [writingSection, setWritingSection] = useState<string | null>(null)
  const [writingRunning, setWritingRunning] = useState(false)
  const [sectionsContent, setSectionsContent] = useState<Record<string, SectionDraft>>({})
  const [activeTab, setActiveTab] = useState<'outline' | 'writing'>('outline')
  const [customRequest, setCustomRequest] = useState('')
  const [reviewingSection, setReviewingSection] = useState<string | null>(null)
  const [reviewRunning, setReviewRunning] = useState(false)
  const [hitlSections, setHitlSections] = useState<Set<string>>(new Set())

  const abortRef = useRef<AbortController | null>(null)
  const writeAbortRef = useRef<AbortController | null>(null)
  const reviewAbortRef = useRef<AbortController | null>(null)
  const traceEndRef = useRef<HTMLDivElement>(null)

  const loadProject = async () => {
    const { data } = await api.get(`/agent/projects/${projectId}`)
    setProject(data)
    if (data.sections_content) {
      setSectionsContent(data.sections_content)
    }
  }

  const loadTraces = async () => {
    const { data } = await api.get(`/agent/projects/${projectId}/traces`)
    setTraces(data)
  }

  useEffect(() => {
    loadProject()
    loadTraces()
  }, [projectId])

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [traces])

  // ── SSE 工具 ──────────────────────────────────────────────────────────────

  const addTrace = (ev: TraceEvent) => setTraces(prev => [...prev, ev])

  const handleSseEvent = (ev: Record<string, unknown>) => {
    const type = ev.type as string
    const agent = (ev.agent as string) ?? '系统'

    switch (type) {
      case 'coordinator_start':
      case 'coordinator_plan':
      case 'session_done':
        addTrace({
          agent_name: '协调器',
          action_type: 'start',
          content: (ev.message as string) ?? (ev.reason as string) ?? type,
          timestamp: new Date().toISOString(),
        })
        break
      case 'agent_start':
        addTrace({ agent_name: agent, action_type: 'start', content: ev.message as string, timestamp: new Date().toISOString() })
        break
      case 'think':
        addTrace({ agent_name: agent, action_type: 'think', content: ev.content as string, timestamp: new Date().toISOString() })
        break
      case 'tool_call':
        addTrace({
          agent_name: agent, action_type: 'tool_call',
          content: JSON.stringify(ev.args ?? {}),
          tool_name: ev.tool as string,
          timestamp: new Date().toISOString(),
        })
        break
      case 'tool_result':
        addTrace({
          agent_name: agent, action_type: 'tool_result',
          content: ev.preview as string,
          tool_name: ev.tool as string,
          latency_ms: ev.latency_ms as number,
          timestamp: new Date().toISOString(),
        })
        break
      case 'agent_done':
        addTrace({ agent_name: agent, action_type: 'output', content: ev.content as string, timestamp: new Date().toISOString() })
        break
      case 'outline_ready':
        setProject(prev => prev ? { ...prev, outline: ev.outline as Outline, outline_status: 'pending' } : prev)
        addTrace({ agent_name: agent, action_type: 'output', content: '大纲已生成，等待您确认', timestamp: new Date().toISOString() })
        break
      case 'section_draft': {
        const sid = ev.section_id as string
        const draft: SectionDraft = {
          content: ev.content as string,
          citations: (ev.citations as string[]) ?? [],
          word_count: (ev.word_count as number) ?? 0,
          status: 'draft',
        }
        setSectionsContent(prev => ({ ...prev, [sid]: draft }))
        addTrace({
          agent_name: agent, action_type: 'output',
          content: `章节草稿完成，${draft.word_count} 字`,
          timestamp: new Date().toISOString(),
        })
        break
      }
      case 'review_result': {
        const sid = ev.section_id as string
        const review = ev.review as ReviewResult
        setSectionsContent(prev => {
          const existing = prev[sid] ?? { content: '', citations: [], word_count: 0, status: 'draft' as const }
          return { ...prev, [sid]: { ...existing, review } }
        })
        addTrace({
          agent_name: agent, action_type: 'output',
          content: `评审完成，综合评分 ${review.overall_score.toFixed(1)}/5.0`,
          timestamp: new Date().toISOString(),
        })
        break
      }
      case 'review_hitl': {
        const sid = ev.section_id as string
        setHitlSections(prev => new Set([...prev, sid]))
        addTrace({
          agent_name: agent, action_type: 'output',
          content: `评分偏低（${(ev.overall_score as number).toFixed(1)}/5.0），等待您决策`,
          timestamp: new Date().toISOString(),
        })
        break
      }
      case 'error':
        addTrace({ agent_name: agent, action_type: 'error', content: (ev.message ?? ev.content) as string, timestamp: new Date().toISOString() })
        break
    }
  }

  // ── 运行协调器 ────────────────────────────────────────────────────────────

  const runAgent = async (request: string) => {
    if (running || writingRunning) return
    setRunning(true)
    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const resp = await fetch(`/api/agent/projects/${projectId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request }),
        signal: ctrl.signal,
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        addTrace({ agent_name: '系统', action_type: 'error', content: err.detail || '请求失败', timestamp: new Date().toISOString() })
        return
      }
      await consumeSse(resp, handleSseEvent)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        addTrace({ agent_name: '系统', action_type: 'error', content: String(e), timestamp: new Date().toISOString() })
      }
    } finally {
      setRunning(false)
      abortRef.current = null
      await loadProject()
      await loadTraces()
    }
  }

  // ── 章节写作 ──────────────────────────────────────────────────────────────

  const writeSection = async (section: OutlineSection) => {
    if (running || writingRunning) return
    setWritingSection(section.id)
    setWritingRunning(true)
    setActiveTab('writing')
    const ctrl = new AbortController()
    writeAbortRef.current = ctrl

    try {
      const resp = await fetch(
        `/api/agent/projects/${projectId}/sections/${section.id}/write`,
        { method: 'POST', signal: ctrl.signal }
      )
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        addTrace({ agent_name: '系统', action_type: 'error', content: err.detail || '写作失败', timestamp: new Date().toISOString() })
        return
      }
      await consumeSse(resp, handleSseEvent)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        addTrace({ agent_name: '系统', action_type: 'error', content: String(e), timestamp: new Date().toISOString() })
      }
    } finally {
      setWritingRunning(false)
      setWritingSection(null)
      writeAbortRef.current = null
      await loadTraces()
    }
  }

  // ── 章节评审 ──────────────────────────────────────────────────────────────

  const reviewSection = async (section: OutlineSection) => {
    if (running || writingRunning || reviewRunning) return
    setReviewingSection(section.id)
    setReviewRunning(true)
    // 展开对应章节卡片，确保评审结果可见（通过切换到写作标签）
    setActiveTab('writing')
    const ctrl = new AbortController()
    reviewAbortRef.current = ctrl

    try {
      const resp = await fetch(
        `/api/agent/projects/${projectId}/sections/${section.id}/review`,
        { method: 'POST', signal: ctrl.signal }
      )
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        addTrace({ agent_name: '系统', action_type: 'error', content: err.detail || '评审失败', timestamp: new Date().toISOString() })
        return
      }
      await consumeSse(resp, handleSseEvent)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        addTrace({ agent_name: '系统', action_type: 'error', content: String(e), timestamp: new Date().toISOString() })
      }
    } finally {
      setReviewRunning(false)
      setReviewingSection(null)
      reviewAbortRef.current = null
      await loadTraces()
    }
  }

  const dismissHitl = (sectionId: string) => {
    setHitlSections(prev => { const s = new Set(prev); s.delete(sectionId); return s })
  }

  // ── HITL 确认大纲 ─────────────────────────────────────────────────────────

  const confirmOutline = async (outline: Outline) => {
    await api.post(`/agent/projects/${projectId}/outline/confirm`, { outline })
    await loadProject()
  }

  if (!project) {
    return <div className="h-full flex items-center justify-center text-slate-500">加载中...</div>
  }

  const isAnyRunning = running || writingRunning || reviewRunning

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 顶栏 */}
      <div className="shrink-0 px-6 py-3 border-b border-slate-700/50 flex items-center gap-4">
        <button
          onClick={() => navigate('/thesis')}
          className="text-slate-400 hover:text-white transition-colors text-sm"
        >
          ← 返回
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-base font-semibold text-white truncate">{project.title}</h1>
          <p className="text-xs text-slate-400 truncate">{project.topic}</p>
        </div>
        <div className="flex gap-2 shrink-0">
          {isAnyRunning ? (
            <button
              onClick={() => { abortRef.current?.abort(); writeAbortRef.current?.abort(); reviewAbortRef.current?.abort() }}
              className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-xs transition-colors"
            >
              停止
            </button>
          ) : (
            <>
              <button
                onClick={() => runAgent('帮我进行文献研究并生成论文大纲')}
                className="px-3 py-1.5 bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg text-xs font-medium transition-colors"
              >
                运行完整流程
              </button>
              <button
                onClick={() => runAgent('只进行文献研究，不生成大纲')}
                className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs transition-colors"
              >
                仅文献研究
              </button>
            </>
          )}
        </div>
      </div>

      {/* 主体：左右分栏 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左栏：Agent Trace */}
        <div className="w-96 shrink-0 flex flex-col border-r border-slate-700/50 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-200">Agent 活动追踪</span>
            {isAnyRunning && (
              <span className="flex items-center gap-1.5 text-xs text-indigo-400">
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse" />
                {writingRunning ? '写作中' : reviewRunning ? '评审中' : '运行中'}
              </span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-2">
            {traces.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-8">
                点击「运行完整流程」或在写作工坊中启动章节写作
              </p>
            ) : (
              traces.map((ev, i) => <TraceItem key={i} ev={ev} />)
            )}
            <div ref={traceEndRef} />
          </div>

          {/* 自定义指令输入 */}
          <div className="shrink-0 px-4 py-3 border-t border-slate-700/50">
            <div className="flex gap-2">
              <input
                className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                placeholder="自定义指令..."
                value={customRequest}
                onChange={e => setCustomRequest(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && customRequest.trim() && !isAnyRunning) {
                    runAgent(customRequest.trim())
                    setCustomRequest('')
                  }
                }}
              />
              <button
                disabled={isAnyRunning || !customRequest.trim()}
                onClick={() => { runAgent(customRequest.trim()); setCustomRequest('') }}
                className="px-3 py-2 bg-indigo-500 hover:bg-indigo-400 disabled:opacity-40 text-white rounded-lg text-xs transition-colors"
              >
                发送
              </button>
            </div>
          </div>
        </div>

        {/* 右栏：标签切换 */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* 标签栏 */}
          <div className="shrink-0 flex border-b border-slate-700/50 px-6">
            {(['outline', 'writing'] as const).map(tab => {
              const label = tab === 'outline' ? '大纲规划' : '写作工坊'
              const hasContent = tab === 'writing'
                ? project.outline_status === 'confirmed'
                : !!project.outline
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab
                      ? 'border-indigo-400 text-indigo-300'
                      : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {label}
                  {tab === 'writing' && !hasContent && (
                    <span className="ml-2 text-xs text-slate-600">（需先确认大纲）</span>
                  )}
                  {tab === 'writing' && hasContent && Object.keys(sectionsContent).length > 0 && (
                    <span className="ml-1.5 px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 rounded-full text-xs">
                      {Object.keys(sectionsContent).length}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* 标签内容 */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'outline' && (
              project.outline ? (
                <OutlineView
                  outline={project.outline}
                  status={project.outline_status}
                  onConfirm={confirmOutline}
                />
              ) : (
                <EmptyOutlinePlaceholder />
              )
            )}

            {activeTab === 'writing' && (
              project.outline_status === 'confirmed' && project.outline ? (
                <WritingView
                  outline={project.outline}
                  sectionsContent={sectionsContent}
                  writingSection={writingSection}
                  writingRunning={writingRunning}
                  reviewingSection={reviewingSection}
                  reviewRunning={reviewRunning}
                  hitlSections={hitlSections}
                  onWrite={writeSection}
                  onReview={reviewSection}
                  onDismissHitl={dismissHitl}
                />
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center gap-3">
                  <div className="w-14 h-14 bg-slate-800 rounded-2xl flex items-center justify-center text-2xl">✏️</div>
                  <p className="text-slate-300 font-medium">请先在「大纲规划」中确认大纲</p>
                  <p className="text-slate-500 text-sm">确认大纲后方可逐章撰写</p>
                  <button
                    onClick={() => setActiveTab('outline')}
                    className="mt-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
                  >
                    前往大纲规划
                  </button>
                </div>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── 工具函数 ──────────────────────────────────────────────────────────────────

async function consumeSse(
  resp: Response,
  handler: (ev: Record<string, unknown>) => void
) {
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try { handler(JSON.parse(line.slice(6))) } catch { /* skip */ }
    }
  }
}

function EmptyOutlinePlaceholder() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center gap-4">
      <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center text-3xl">📝</div>
      <div>
        <p className="text-slate-300 font-medium">等待生成大纲</p>
        <p className="text-slate-500 text-sm mt-1">
          运行完整流程后，Agent 将搜集文献并自动生成论文大纲
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center mt-2">
        {['文献研究 Agent', '大纲规划 Agent', 'Human-in-the-Loop'].map(tag => (
          <span key={tag} className="px-2 py-1 bg-slate-800 text-slate-500 rounded text-xs">{tag}</span>
        ))}
      </div>
    </div>
  )
}
