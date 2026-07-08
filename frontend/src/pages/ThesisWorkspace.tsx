import { useEffect, useRef, useState, type ComponentType } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Play, Brain, Wrench, Check, FileText, X, Send, Square,
  Sparkles, PenLine, ChevronDown, Upload, Route, ShieldCheck, ClipboardList,
} from 'lucide-react'
import axios from 'axios'
import { toast } from 'sonner'
import { Button, Badge, Input, Dialog, Textarea } from '../components/ui'
import Markdown from '../components/Markdown'
import { cn } from '../lib/cn'

const api = axios.create({ baseURL: '/api' })

// ── 类型 ──────────────────────────────────────────────────────────────────────

interface OutlineSection { id: string; title: string; key_points: string[]; estimated_words: number; requirement?: string; level?: number }
interface Outline { title: string; abstract_hint: string; research_gap: string; sections: OutlineSection[] }
interface ReviewResult {
  logic_score: number; academic_tone: number; citation_coverage: number; argument_support: number
  overall_score: number; strengths: string[]; suggestions: string[]; rewrite_needed: boolean
}
interface SectionDraft { content: string; citations: string[]; word_count: number; status: 'draft'; review?: ReviewResult }
interface TraceEvent {
  agent_name: string; action_type: string; content: string
  tool_name?: string | null; latency_ms?: number | null; timestamp: string
}
interface Project {
  id: number; title: string; topic: string; kb_id: number | null; outline_status: string
  outline: Outline | null; literature_notes: Record<string, unknown> | null
  sections_content: Record<string, SectionDraft> | null
}

// ── Trace 样式 ────────────────────────────────────────────────────────────────

const ACTION: Record<string, { icon: ComponentType<{ className?: string }>; cls: string; label: string }> = {
  start: { icon: Play, cls: 'text-indigo-500', label: '启动' },
  think: { icon: Brain, cls: 'text-slate-400', label: '推理' },
  tool_call: { icon: Wrench, cls: 'text-amber-500', label: '工具调用' },
  tool_result: { icon: Check, cls: 'text-emerald-500', label: '工具结果' },
  output: { icon: FileText, cls: 'text-blue-500', label: '输出' },
  error: { icon: X, cls: 'text-rose-500', label: '错误' },
}

function TraceItem({ ev }: { ev: TraceEvent }) {
  const s = ACTION[ev.action_type] ?? { icon: FileText, cls: 'text-slate-400', label: ev.action_type }
  const Icon = s.icon
  return (
    <div className="flex gap-2.5 border-b border-slate-100 py-2 last:border-0">
      <Icon className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', s.cls)} />
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 flex items-center gap-1.5">
          <span className="text-xs font-medium text-slate-600">{ev.agent_name}</span>
          <span className={cn('text-xs', s.cls)}>{s.label}</span>
          {ev.tool_name && <Badge tone="amber">{ev.tool_name}</Badge>}
          {ev.latency_ms != null && <span className="ml-auto text-xs text-slate-300">{ev.latency_ms}ms</span>}
        </div>
        <p className="line-clamp-2 text-xs text-slate-400">{ev.content}</p>
      </div>
    </div>
  )
}

// ── 大纲 ──────────────────────────────────────────────────────────────────────

function OutlineView({ outline, status, onConfirm, onOpenSection }: { outline: Outline; status: string; onConfirm: (o: Outline) => void; onOpenSection: (id: string) => void }) {
  const totalWords = outline.sections.reduce((s, sec) => s + sec.estimated_words, 0)
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-800">{outline.title}</h3>
          <p className="mt-1 text-xs text-slate-400">{outline.abstract_hint}</p>
        </div>
        <Badge tone={status === 'confirmed' ? 'emerald' : 'amber'}>{status === 'confirmed' ? '已确认' : '待确认'}</Badge>
      </div>

      <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 px-4 py-3">
        <p className="mb-1 text-xs font-medium text-indigo-600">研究空白 / 创新点</p>
        <p className="text-sm text-slate-600">{outline.research_gap}</p>
      </div>

      <div className="space-y-2">
        {outline.sections.map((sec, idx) => (
          <div key={sec.id} className="rounded-xl border border-slate-200 bg-white p-3.5" style={{ marginLeft: `${Math.max(0, (sec.level ?? 1) - 1) * 18}px` }}>
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-700">{idx + 1}. {sec.title}</span>
              <div className="flex shrink-0 items-center gap-2">
                {sec.level && <Badge tone="slate">L{sec.level}</Badge>}
                <span className="text-xs text-slate-400">{sec.estimated_words.toLocaleString()} 字</span>
                <Button size="sm" variant="ghost" onClick={() => onOpenSection(sec.id)} className="text-indigo-600 hover:bg-indigo-50"><PenLine className="h-3.5 w-3.5" />进入生成页</Button>
              </div>
            </div>
            <ul className="space-y-1">
              {sec.key_points.map((kp, ki) => (
                <li key={ki} className="flex gap-2 text-xs text-slate-500"><span className="shrink-0 text-slate-300">·</span>{kp}</li>
              ))}
            </ul>
            {sec.requirement && (
              <p className="mt-2 rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs text-slate-500"><span className="font-medium text-slate-400">写作要求：</span>{sec.requirement}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs text-slate-400">预计总字数：{totalWords.toLocaleString()} 字</span>
        {status !== 'confirmed' ? (
          <Button size="sm" onClick={() => onConfirm(outline)}><Check className="h-3.5 w-3.5" />确认大纲</Button>
        ) : (
          <span className="text-xs font-medium text-emerald-600">大纲已确认，可前往写作工坊</span>
        )}
      </div>
    </div>
  )
}

// ── 评审 ──────────────────────────────────────────────────────────────────────

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round((score / 5) * 100)
  const color = score >= 4 ? 'bg-emerald-500' : score >= 3 ? 'bg-amber-500' : 'bg-rose-500'
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 shrink-0 text-xs text-slate-400">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-xs text-slate-500">{score.toFixed(1)}</span>
    </div>
  )
}

function ReviewCard({ review, hitlPending, onRewrite, onDismiss }: {
  review: ReviewResult; hitlPending: boolean; onRewrite: () => void; onDismiss: () => void
}) {
  const overall = review.overall_score
  const overallColor = overall >= 4 ? 'text-emerald-600' : overall >= 3 ? 'text-amber-600' : 'text-rose-600'
  return (
    <div className={cn('space-y-3 rounded-xl border p-3.5', hitlPending ? 'border-amber-200 bg-amber-50/60' : 'border-slate-200 bg-slate-50/60')}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-600">学术评审结果（LLM-as-Judge）</span>
        <span className={cn('text-sm font-bold', overallColor)}>{overall.toFixed(1)}<span className="text-xs font-normal text-slate-400">/5.0</span></span>
      </div>
      <div className="space-y-1.5">
        <ScoreBar label="逻辑严密性" score={review.logic_score} />
        <ScoreBar label="学术规范性" score={review.academic_tone} />
        <ScoreBar label="引用充分度" score={review.citation_coverage} />
        <ScoreBar label="论点支撑度" score={review.argument_support} />
      </div>
      {review.suggestions.length > 0 && (
        <div>
          <p className="mb-1 text-xs text-slate-400">改进建议：</p>
          <ul className="space-y-0.5">
            {review.suggestions.map((s, i) => <li key={i} className="flex gap-1.5 text-xs text-slate-500"><span className="shrink-0 text-amber-500">·</span>{s}</li>)}
          </ul>
        </div>
      )}
      {hitlPending && (
        <div className="border-t border-amber-200 pt-2">
          <p className="mb-2 text-xs text-amber-600">综合评分偏低，建议重新写作：</p>
          <div className="flex gap-2">
            <Button size="sm" onClick={onRewrite}>接受建议，重新写作</Button>
            <Button size="sm" variant="secondary" onClick={onDismiss}>忽略，保留草稿</Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── 章节卡 ────────────────────────────────────────────────────────────────────

function SectionCard({ section, idx, draft, isWriting, isReviewing, hitlPending, onWrite, onReview, onDismissHitl }: {
  section: OutlineSection; idx: number; draft: SectionDraft | undefined
  isWriting: boolean; isReviewing: boolean; hitlPending: boolean
  onWrite: (s: OutlineSection) => void; onReview: (s: OutlineSection) => void; onDismissHitl: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const isActive = isWriting || isReviewing
  return (
    <div
      className={cn('rounded-xl border bg-white transition-colors',
        isWriting ? 'border-indigo-300 shadow-soft' : isReviewing ? 'border-violet-300 shadow-soft' : 'border-slate-200 hover:border-slate-300')}
      style={{ marginLeft: `${Math.max(0, (section.level ?? 1) - 1) * 18}px` }}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <span className="shrink-0 font-mono text-xs text-slate-400">§{idx + 1}</span>
              <h4 className="truncate text-sm font-medium text-slate-700">{section.title}</h4>
              {section.level && <Badge tone="slate">L{section.level}</Badge>}
              {draft && <Badge tone="emerald">草稿 {draft.word_count}字</Badge>}
              {draft?.review && <Badge tone={draft.review.overall_score >= 4 ? 'emerald' : draft.review.overall_score >= 3 ? 'amber' : 'rose'}>评分 {draft.review.overall_score.toFixed(1)}</Badge>}
              {isWriting && <span className="flex items-center gap-1 text-xs text-indigo-500"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" />写作中</span>}
              {isReviewing && <span className="flex items-center gap-1 text-xs text-violet-500"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" />评审中</span>}
            </div>
            <div className="flex flex-wrap gap-1">
              {section.key_points.slice(0, 3).map((kp, i) => (
                <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">{kp.length > 20 ? kp.slice(0, 20) + '…' : kp}</span>
              ))}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {draft && <Button size="sm" variant="ghost" onClick={() => setExpanded(v => !v)}><ChevronDown className={cn('h-3.5 w-3.5 transition-transform', expanded && 'rotate-180')} />{expanded ? '收起' : '查看'}</Button>}
            {draft && <Button size="sm" variant="outline" disabled={isActive} onClick={() => onReview(section)} className="text-violet-600 hover:border-violet-300 hover:bg-violet-50">{isReviewing ? '评审中' : '评审'}</Button>}
            <Button size="sm" variant={draft ? 'secondary' : 'primary'} disabled={isActive} onClick={() => onWrite(section)}>{isWriting ? '写作中' : draft ? '重写' : '写作'}</Button>
          </div>
        </div>
      </div>

      {expanded && draft && (
        <div className="space-y-3 border-t border-slate-100 px-4 py-3">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>共 {draft.word_count} 字</span>
            {draft.citations.length > 0 && <span>· {draft.citations.length} 处引用</span>}
          </div>
          <div className="max-h-72 overflow-y-auto rounded-xl border border-slate-100 bg-slate-50/40 p-3.5">
            <Markdown content={draft.content} />
          </div>
          {draft.citations.length > 0 && (
            <div className="space-y-0.5">
              <p className="text-xs font-medium text-slate-400">引用来源：</p>
              {draft.citations.map((c, i) => <p key={i} className="pl-2 text-xs text-slate-400">· {c}</p>)}
            </div>
          )}
          {draft.review && (
            <ReviewCard review={draft.review} hitlPending={hitlPending}
              onRewrite={() => { onWrite(section); onDismissHitl(section.id) }}
              onDismiss={() => onDismissHitl(section.id)} />
          )}
        </div>
      )}
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
  const [workflowRunning, setWorkflowRunning] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importTitle, setImportTitle] = useState('未完成论文初稿')
  const [importContent, setImportContent] = useState('')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const writeAbortRef = useRef<AbortController | null>(null)
  const reviewAbortRef = useRef<AbortController | null>(null)
  const workflowAbortRef = useRef<AbortController | null>(null)
  const traceEndRef = useRef<HTMLDivElement>(null)

  const loadProject = async () => {
    const { data } = await api.get(`/agent/projects/${projectId}`)
    setProject(data)
    if (data.sections_content) setSectionsContent(data.sections_content)
  }
  const loadTraces = async () => {
    const { data } = await api.get(`/agent/projects/${projectId}/traces`)
    setTraces(data)
  }

  useEffect(() => { loadProject(); loadTraces() }, [projectId])
  useEffect(() => { traceEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [traces])

  const addTrace = (ev: TraceEvent) => setTraces(prev => [...prev, ev])

  const handleSseEvent = (ev: Record<string, unknown>) => {
    const type = ev.type as string
    const agent = (ev.agent as string) ?? '系统'
    const now = () => new Date().toISOString()
    switch (type) {
      case 'coordinator_start':
      case 'coordinator_plan':
      case 'session_done':
        addTrace({ agent_name: '协调器', action_type: 'start', content: (ev.message as string) ?? (ev.reason as string) ?? type, timestamp: now() })
        break
      case 'supervisor_plan':
        addTrace({ agent_name: 'Supervisor', action_type: 'start', content: `${ev.action as string}${ev.section ? ` · ${ev.section as string}` : ''}：${ev.reason as string}`, timestamp: now() })
        break
      case 'workflow_paused':
        addTrace({ agent_name: 'Supervisor', action_type: 'output', content: (ev.message as string) ?? (ev.reason as string) ?? '工作流已暂停', timestamp: now() })
        break
      case 'workflow_halt':
        addTrace({ agent_name: 'Supervisor', action_type: 'error', content: (ev.reason as string) ?? '工作流已停止', timestamp: now() })
        break
      case 'agent_start':
        addTrace({ agent_name: agent, action_type: 'start', content: ev.message as string, timestamp: now() })
        break
      case 'think':
        addTrace({ agent_name: agent, action_type: 'think', content: ev.content as string, timestamp: now() })
        break
      case 'tool_call':
        addTrace({ agent_name: agent, action_type: 'tool_call', content: JSON.stringify(ev.args ?? {}), tool_name: ev.tool as string, timestamp: now() })
        break
      case 'tool_result':
        addTrace({ agent_name: agent, action_type: 'tool_result', content: ev.preview as string, tool_name: ev.tool as string, latency_ms: ev.latency_ms as number, timestamp: now() })
        break
      case 'agent_done':
        addTrace({ agent_name: agent, action_type: 'output', content: ev.content as string, timestamp: now() })
        break
      case 'outline_ready':
        setProject(prev => prev ? { ...prev, outline: ev.outline as Outline, outline_status: 'pending' } : prev)
        addTrace({ agent_name: agent, action_type: 'output', content: '大纲已生成，等待您确认', timestamp: now() })
        break
      case 'section_draft': {
        const sid = ev.section_id as string
        const draft: SectionDraft = { content: ev.content as string, citations: (ev.citations as string[]) ?? [], word_count: (ev.word_count as number) ?? 0, status: 'draft' }
        setSectionsContent(prev => ({ ...prev, [sid]: draft }))
        addTrace({ agent_name: agent, action_type: 'output', content: `章节草稿完成，${draft.word_count} 字`, timestamp: now() })
        break
      }
      case 'review_result': {
        const sid = ev.section_id as string
        const review = ev.review as ReviewResult
        setSectionsContent(prev => {
          const existing = prev[sid] ?? { content: '', citations: [], word_count: 0, status: 'draft' as const }
          return { ...prev, [sid]: { ...existing, review } }
        })
        addTrace({ agent_name: agent, action_type: 'output', content: `评审完成，综合评分 ${review.overall_score.toFixed(1)}/5.0`, timestamp: now() })
        break
      }
      case 'review_hitl': {
        const sid = ev.section_id as string
        setHitlSections(prev => new Set([...prev, sid]))
        addTrace({ agent_name: agent, action_type: 'output', content: `评分偏低（${(ev.overall_score as number).toFixed(1)}/5.0），等待您决策`, timestamp: now() })
        break
      }
      case 'citation_report': {
        const total = (ev.total as number) ?? 0
        const accuracy = Math.round(((ev.citation_accuracy as number) ?? 0) * 100)
        addTrace({ agent_name: agent, action_type: 'tool_result', content: `引用核验完成：${total} 条，准确率 ${accuracy}%`, tool_name: 'citation_verifier', timestamp: now() })
        break
      }
      case 'error':
        addTrace({ agent_name: agent, action_type: 'error', content: (ev.message ?? ev.content) as string, timestamp: now() })
        break
    }
  }

  const runAgent = async (request: string) => {
    if (running || writingRunning) return
    setRunning(true)
    const ctrl = new AbortController(); abortRef.current = ctrl
    try {
      const resp = await fetch(`/api/agent/projects/${projectId}/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ request }), signal: ctrl.signal })
      if (!resp.ok) { const err = await resp.json().catch(() => ({})); addTrace({ agent_name: '系统', action_type: 'error', content: err.detail || '请求失败', timestamp: new Date().toISOString() }); return }
      await consumeSse(resp, handleSseEvent)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') addTrace({ agent_name: '系统', action_type: 'error', content: String(e), timestamp: new Date().toISOString() })
    } finally { setRunning(false); abortRef.current = null; await loadProject(); await loadTraces() }
  }

  const generateOutline = async (withLit: boolean) => {
    if (running || writingRunning || reviewRunning) return
    setRunning(true); setActiveTab('outline')
    const ctrl = new AbortController(); abortRef.current = ctrl
    try {
      const resp = await fetch(`/api/agent/projects/${projectId}/outline/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ with_literature: withLit }), signal: ctrl.signal })
      if (!resp.ok) { const err = await resp.json().catch(() => ({})); addTrace({ agent_name: '系统', action_type: 'error', content: err.detail || '生成失败', timestamp: new Date().toISOString() }); return }
      await consumeSse(resp, handleSseEvent)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') addTrace({ agent_name: '系统', action_type: 'error', content: String(e), timestamp: new Date().toISOString() })
    } finally { setRunning(false); abortRef.current = null; await loadProject(); await loadTraces() }
  }

  const runWorkflow = async () => {
    if (running || writingRunning || reviewRunning || workflowRunning) return
    setWorkflowRunning(true)
    const ctrl = new AbortController(); workflowAbortRef.current = ctrl
    try {
      const resp = await fetch(`/api/agent/projects/${projectId}/workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request: '执行完整论文写作工作流' }),
        signal: ctrl.signal,
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        addTrace({ agent_name: '系统', action_type: 'error', content: err.detail || '自动工作流启动失败', timestamp: new Date().toISOString() })
        return
      }
      await consumeSse(resp, handleSseEvent)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') addTrace({ agent_name: '系统', action_type: 'error', content: String(e), timestamp: new Date().toISOString() })
    } finally {
      setWorkflowRunning(false)
      workflowAbortRef.current = null
      await loadProject()
      await loadTraces()
    }
  }

  const writeSection = async (section: OutlineSection) => {
    if (running || writingRunning) return
    setWritingSection(section.id); setWritingRunning(true); setActiveTab('writing')
    const ctrl = new AbortController(); writeAbortRef.current = ctrl
    try {
      const resp = await fetch(`/api/agent/projects/${projectId}/sections/${section.id}/write`, { method: 'POST', signal: ctrl.signal })
      if (!resp.ok) { const err = await resp.json().catch(() => ({})); addTrace({ agent_name: '系统', action_type: 'error', content: err.detail || '写作失败', timestamp: new Date().toISOString() }); return }
      await consumeSse(resp, handleSseEvent)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') addTrace({ agent_name: '系统', action_type: 'error', content: String(e), timestamp: new Date().toISOString() })
    } finally { setWritingRunning(false); setWritingSection(null); writeAbortRef.current = null; await loadTraces() }
  }

  const reviewSection = async (section: OutlineSection) => {
    if (running || writingRunning || reviewRunning) return
    setReviewingSection(section.id); setReviewRunning(true); setActiveTab('writing')
    const ctrl = new AbortController(); reviewAbortRef.current = ctrl
    try {
      const resp = await fetch(`/api/agent/projects/${projectId}/sections/${section.id}/review`, { method: 'POST', signal: ctrl.signal })
      if (!resp.ok) { const err = await resp.json().catch(() => ({})); addTrace({ agent_name: '系统', action_type: 'error', content: err.detail || '评审失败', timestamp: new Date().toISOString() }); return }
      await consumeSse(resp, handleSseEvent)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') addTrace({ agent_name: '系统', action_type: 'error', content: String(e), timestamp: new Date().toISOString() })
    } finally { setReviewRunning(false); setReviewingSection(null); reviewAbortRef.current = null; await loadTraces() }
  }

  const dismissHitl = (sectionId: string) => setHitlSections(prev => { const s = new Set(prev); s.delete(sectionId); return s })

  const importDraft = async () => {
    if (!importContent.trim() && !importFile) return
    setImporting(true)
    try {
      if (importFile) {
        const fd = new FormData()
        fd.append('file', importFile)
        await api.post(`/agent/projects/${projectId}/import-document`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        await api.post(`/agent/projects/${projectId}/import-draft`, {
          title: importTitle.trim() || '未完成论文初稿',
          content: importContent.trim(),
        })
      }
      setImportOpen(false)
      setImportContent('')
      setImportFile(null)
      toast.success('初稿已导入，可在写作工作台继续修改')
      await loadProject()
      setActiveTab('writing')
    } catch {
      toast.error('导入失败')
    } finally {
      setImporting(false)
    }
  }

  const readImportFile = async (file: File | undefined) => {
    if (!file) return
    setImportFile(file)
    setImportTitle(file.name.replace(/\.(docx|txt|md)$/i, '') || '未完成论文初稿')
    if (/\.(txt|md)$/i.test(file.name)) {
      const text = await file.text()
      setImportContent(text)
    } else {
      setImportContent('')
    }
  }

  const confirmOutline = async (outline: Outline) => {
    await api.post(`/agent/projects/${projectId}/outline/confirm`, { outline })
    await loadProject()
  }

  if (!project) return <div className="flex h-full items-center justify-center text-sm text-slate-400">加载中…</div>

  const isAnyRunning = running || writingRunning || reviewRunning || workflowRunning
  const writingReady = project.outline_status === 'confirmed' && !!project.outline
  const sections = project.outline?.sections ?? []
  const draftCount = Object.keys(sectionsContent).length
  const reviewCount = Object.values(sectionsContent).filter(d => d.review).length
  const workflowStatus = project.outline_status === 'confirmed'
    ? '大纲已确认，可以进入逐章写作与质量评估'
    : project.outline
      ? '大纲待确认，确认后才能自动写作'
      : '先生成大纲或导入未完成论文'

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* 顶栏 */}
      <div className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-5">
        <button onClick={() => navigate('/writing')} className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"><ArrowLeft className="h-5 w-5" /></button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold text-slate-800">{project.title}</h1>
          <p className="truncate text-xs text-slate-400">{project.topic}</p>
        </div>
        {isAnyRunning ? (
          <Button size="sm" variant="danger" onClick={() => { abortRef.current?.abort(); writeAbortRef.current?.abort(); reviewAbortRef.current?.abort(); workflowAbortRef.current?.abort() }}><Square className="h-3.5 w-3.5" fill="currentColor" />停止</Button>
        ) : (
          <>
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}><Upload className="h-3.5 w-3.5" />导入初稿</Button>
            <Button size="sm" variant="outline" onClick={() => generateOutline(false)}><Sparkles className="h-3.5 w-3.5" />直接生成大纲</Button>
            <Button size="sm" onClick={() => runAgent('帮我进行文献研究并生成论文大纲')}><Play className="h-3.5 w-3.5" />文献研究+大纲</Button>
          </>
        )}
      </div>

      <div className="shrink-0 border-b border-slate-200 bg-slate-50 px-5 py-4">
        <div className="grid gap-3 lg:grid-cols-[1.4fr_0.9fr_0.9fr]">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-soft">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Writing Control</p>
                <h2 className="mt-1 text-base font-semibold text-slate-800">论文生产控制台</h2>
              </div>
              <Badge tone={project.outline_status === 'confirmed' ? 'emerald' : project.outline ? 'amber' : 'slate'}>
                {project.outline_status === 'confirmed' ? '可写作' : project.outline ? '待确认' : '未规划'}
              </Badge>
            </div>
            <p className="text-sm text-slate-500">{workflowStatus}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button size="sm" onClick={runWorkflow} disabled={isAnyRunning}><Route className="h-3.5 w-3.5" />自动闭环工作流</Button>
              <Button size="sm" variant="outline" onClick={() => setActiveTab('outline')}><ClipboardList className="h-3.5 w-3.5" />查看大纲</Button>
              <Button size="sm" variant="outline" onClick={() => setActiveTab('writing')} disabled={!writingReady}><PenLine className="h-3.5 w-3.5" />进入写作</Button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-soft">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <PenLine className="h-4 w-4 text-indigo-500" />
              章节进度
            </div>
            <div className="mt-4 flex items-end gap-2">
              <span className="text-3xl font-semibold text-slate-900">{draftCount}</span>
              <span className="pb-1 text-sm text-slate-400">/ {sections.length || 0} 已起草</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-indigo-500" style={{ width: `${sections.length ? Math.min(100, (draftCount / sections.length) * 100) : 0}%` }} />
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-soft">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              质量闭环
            </div>
            <div className="mt-4 flex items-end gap-2">
              <span className="text-3xl font-semibold text-slate-900">{reviewCount}</span>
              <span className="pb-1 text-sm text-slate-400">章已评审</span>
            </div>
            <p className="mt-3 text-xs text-slate-400">自动工作流会按“写作 → 引用核验 → 评审 → 必要时重写”推进。</p>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* 左栏：Trace */}
        <div className="flex w-96 shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <span className="flex items-center gap-1.5 text-sm font-medium text-slate-700"><Sparkles className="h-4 w-4 text-indigo-500" />Agent 活动追踪</span>
            {isAnyRunning && <span className="flex items-center gap-1.5 text-xs text-indigo-500"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" />{writingRunning ? '写作中' : reviewRunning ? '评审中' : '运行中'}</span>}
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-2">
            {traces.length === 0 ? (
              <p className="py-8 text-center text-xs text-slate-400">点击「运行完整流程」或在写作工坊启动章节写作</p>
            ) : traces.map((ev, i) => <TraceItem key={i} ev={ev} />)}
            <div ref={traceEndRef} />
          </div>
          <div className="shrink-0 border-t border-slate-100 p-3">
            <div className="flex gap-2">
              <Input value={customRequest} onChange={e => setCustomRequest(e.target.value)} placeholder="自定义指令…" className="h-9 flex-1 text-xs"
                onKeyDown={e => { if (e.key === 'Enter' && customRequest.trim() && !isAnyRunning) { runAgent(customRequest.trim()); setCustomRequest('') } }} />
              <Button size="icon" disabled={isAnyRunning || !customRequest.trim()} onClick={() => { runAgent(customRequest.trim()); setCustomRequest('') }}><Send className="h-4 w-4" /></Button>
            </div>
          </div>
        </div>

        {/* 右栏 */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex shrink-0 gap-1 border-b border-slate-200 bg-white px-5">
            {(['outline', 'writing'] as const).map(tab => {
              const label = tab === 'outline' ? '大纲规划' : '写作工坊'
              const ready = tab === 'writing' ? writingReady : !!project.outline
              return (
                <button key={tab} onClick={() => setActiveTab(tab)}
                  className={cn('flex items-center gap-1.5 border-b-2 px-4 py-3 text-sm font-medium transition-colors',
                    activeTab === tab ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-slate-400 hover:text-slate-600')}>
                  {label}
                  {tab === 'writing' && !ready && <span className="text-xs text-slate-300">（需先确认大纲）</span>}
                  {tab === 'writing' && ready && Object.keys(sectionsContent).length > 0 && <Badge tone="emerald">{Object.keys(sectionsContent).length}</Badge>}
                </button>
              )
            })}
          </div>

          <div className="flex-1 overflow-y-auto bg-slate-50 p-6">
            {activeTab === 'outline' && (
              project.outline
                ? <div className="mx-auto max-w-3xl"><OutlineView outline={project.outline} status={project.outline_status} onConfirm={confirmOutline} onOpenSection={(sid) => navigate(`/writing/${projectId}/section/${sid}`)} /></div>
                : <EmptyState icon={FileText} title="等待生成大纲" desc="运行完整流程后，Agent 将搜集文献并自动生成论文大纲" tags={['文献研究 Agent', '大纲规划 Agent', 'Human-in-the-Loop']} />
            )}
            {activeTab === 'writing' && (
              writingReady && project.outline ? (
                <div className="mx-auto max-w-3xl space-y-4">
                  <WritingHeader outline={project.outline} sectionsContent={sectionsContent} />
                  {project.outline.sections.map((sec, idx) => (
                    <SectionCard key={sec.id} section={sec} idx={idx} draft={sectionsContent[sec.id]}
                      isWriting={writingSection === sec.id && writingRunning}
                      isReviewing={reviewingSection === sec.id && reviewRunning}
                      hitlPending={hitlSections.has(sec.id)}
                      onWrite={writeSection} onReview={reviewSection} onDismissHitl={dismissHitl} />
                  ))}
                </div>
              ) : (
                <EmptyState icon={PenLine} title="请先确认大纲" desc="在「大纲规划」中确认大纲后，方可逐章撰写"
                  action={<Button size="sm" variant="secondary" onClick={() => setActiveTab('outline')}>前往大纲规划</Button>} />
              )
            )}
          </div>
        </div>
      </div>

      <Dialog
        open={importOpen}
        onOpenChange={setImportOpen}
        title="导入未完成论文"
        description="支持 .docx 按章节解析，.txt/.md 按标题拆分；也可以直接粘贴正文。导入后会出现在写作工作台。"
        className="max-w-2xl"
      >
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-600">草稿标题</label>
            <Input value={importTitle} onChange={e => setImportTitle(e.target.value)} placeholder="例如：第二章初稿" />
          </div>
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-3">
            <input
              type="file"
              accept=".docx,.txt,.md,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
              onChange={e => readImportFile(e.target.files?.[0])}
              className="text-sm text-slate-500 file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-600"
            />
            {importFile && (
              <p className="mt-2 text-xs text-slate-400">
                已选择：{importFile.name}{/\.docx$/i.test(importFile.name) ? '，将按 Word 标题、摘要、章节和图片解析。' : '，可在下方预览并继续编辑。'}
              </p>
            )}
          </div>
          <Textarea
            rows={10}
            value={importContent}
            onChange={e => setImportContent(e.target.value)}
            placeholder={importFile && /\.docx$/i.test(importFile.name) ? 'Word 文档会直接上传解析；如需覆盖为纯文本导入，可清空文件选择后粘贴正文。' : '把未完成论文正文粘贴到这里。后续可以在章节页逐段精修、保存，并确认生成摘要。'}
          />
          <div className="flex gap-3">
            <Button variant="secondary" className="flex-1" onClick={() => setImportOpen(false)}>取消</Button>
            <Button className="flex-1" loading={importing} disabled={!importContent.trim() && !importFile} onClick={importDraft}>
              <Upload className="h-4 w-4" />导入为草稿
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}

function WritingHeader({ outline, sectionsContent }: { outline: Outline; sectionsContent: Record<string, SectionDraft> }) {
  const draftCount = Object.keys(sectionsContent).length
  const totalWritten = Object.values(sectionsContent).reduce((s, d) => s + d.word_count, 0)
  const reviewedCount = Object.values(sectionsContent).filter(d => d.review).length
  return (
    <div className="flex items-center justify-between">
      <div>
        <h3 className="text-sm font-semibold text-slate-800">章节写作工坊</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          草稿 {draftCount}/{outline.sections.length} 章节{draftCount > 0 && `，共 ${totalWritten.toLocaleString()} 字`}{reviewedCount > 0 && `，已评审 ${reviewedCount} 章`}
        </p>
      </div>
      <div className="flex flex-wrap justify-end gap-1.5">
        {['ReAct', 'Tool Use', 'LLM-as-Judge', 'Long-term Memory'].map(t => <Badge key={t} tone="slate">{t}</Badge>)}
      </div>
    </div>
  )
}

function EmptyState({ icon: Icon, title, desc, tags, action }: {
  icon: ComponentType<{ className?: string }>; title: string; desc: string; tags?: string[]; action?: React.ReactNode
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-indigo-400 shadow-soft"><Icon className="h-7 w-7" /></div>
      <div>
        <p className="font-medium text-slate-700">{title}</p>
        <p className="mt-1 text-sm text-slate-400">{desc}</p>
      </div>
      {tags && <div className="flex flex-wrap justify-center gap-2">{tags.map(t => <Badge key={t} tone="slate">{t}</Badge>)}</div>}
      {action}
    </div>
  )
}

async function consumeSse(resp: Response, handler: (ev: Record<string, unknown>) => void) {
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
