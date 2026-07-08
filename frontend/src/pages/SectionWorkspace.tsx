import { useEffect, useRef, useState, type ComponentType } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Play, Square, Check, Wand2, Brain, Wrench, FileText, X, Sparkles, Save, Pencil,
  Upload, Image as ImageIcon,
} from 'lucide-react'
import axios from 'axios'
import { toast } from 'sonner'
import { Button, Badge, Textarea, Dialog, Spinner, Select } from '../components/ui'
import Markdown from '../components/Markdown'
import { cn } from '../lib/cn'

const api = axios.create({ baseURL: '/api' })

// ── 类型 ──────────────────────────────────────────────────────────────────────

interface KnowledgeBase { id: number; name: string }
interface OutlineSection { id: string; title: string; key_points: string[]; estimated_words: number; requirement?: string; level?: number }
interface Outline { title: string; sections: OutlineSection[] }
interface DraftFormat { font_family: string; font_size: number; line_height: number }
interface SectionDraft { content: string; citations: string[]; word_count: number; format?: DraftFormat }
interface Project {
  id: number; title: string; topic: string; methodology?: string
  kb_id: number | null; kb_ids?: number[]
  outline: Outline | null; outline_status: string
  sections_content: Record<string, SectionDraft> | null
}
interface TraceEvent { agent: string; action_type: string; content: string; tool_name?: string; latency_ms?: number }

const DEFAULT_FORMAT: DraftFormat = { font_family: 'Microsoft YaHei', font_size: 15, line_height: 1.8 }
const FONT_OPTIONS = [
  { value: 'Microsoft YaHei', label: '微软雅黑' },
  { value: 'SimSun', label: '宋体' },
  { value: 'SimHei', label: '黑体' },
  { value: 'Times New Roman', label: 'Times New Roman' },
]
const SIZE_OPTIONS = ['12', '14', '15', '16', '18'].map(v => ({ value: v, label: `${v}px` }))
const LINE_HEIGHT_OPTIONS = ['1.5', '1.8', '2'].map(v => ({ value: v, label: `${v} 倍行距` }))

// ── Trace 行 ──────────────────────────────────────────────────────────────────

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
          <span className="text-xs font-medium text-slate-600">{ev.agent}</span>
          <span className={cn('text-xs', s.cls)}>{s.label}</span>
          {ev.tool_name && <Badge tone="amber">{ev.tool_name}</Badge>}
          {ev.latency_ms != null && <span className="ml-auto text-xs text-slate-300">{ev.latency_ms}ms</span>}
        </div>
        <p className="line-clamp-2 text-xs text-slate-400">{ev.content}</p>
      </div>
    </div>
  )
}

// ── 主页面 ─────────────────────────────────────────────────────────────────────

export default function SectionWorkspace() {
  const { id, sid } = useParams<{ id: string; sid: string }>()
  const navigate = useNavigate()
  const projectId = Number(id)

  const [project, setProject] = useState<Project | null>(null)
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [section, setSection] = useState<OutlineSection | null>(null)
  const [requirement, setRequirement] = useState('')
  const [selectedKbs, setSelectedKbs] = useState<number[]>([])
  const [draft, setDraft] = useState('')
  const [running, setRunning] = useState(false)
  const [savingReq, setSavingReq] = useState(false)
  const [traces, setTraces] = useState<TraceEvent[]>([])
  const [refineIdx, setRefineIdx] = useState<number | null>(null)
  const [refineInstruction, setRefineInstruction] = useState('')
  const [refining, setRefining] = useState(false)
  const [editing, setEditing] = useState(false)
  const [savingDraft, setSavingDraft] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [format, setFormat] = useState<DraftFormat>(DEFAULT_FORMAT)
  const [uploadingImage, setUploadingImage] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const traceEndRef = useRef<HTMLDivElement>(null)

  const projectKbIds = (p: Project) => (p.kb_ids && p.kb_ids.length ? p.kb_ids : (p.kb_id ? [p.kb_id] : []))

  const load = async () => {
    const [{ data: proj }, { data: kbList }] = await Promise.all([
      api.get(`/agent/projects/${projectId}`),
      api.get('/kb'),
    ])
    setProject(proj); setKbs(kbList)
    const sec: OutlineSection | undefined = proj.outline?.sections?.find((s: OutlineSection) => s.id === sid)
    if (sec) { setSection(sec); setRequirement(sec.requirement ?? '') }
    setSelectedKbs(projectKbIds(proj))
    const d = proj.sections_content?.[sid as string]
    if (d) {
      setDraft(d.content)
      setFormat({ ...DEFAULT_FORMAT, ...(d.format ?? {}) })
    }
  }
  useEffect(() => { load() }, [projectId, sid])
  useEffect(() => { traceEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [traces])

  const addTrace = (ev: TraceEvent) => setTraces(prev => [...prev, ev])

  const handleSse = (ev: Record<string, unknown>) => {
    const type = ev.type as string
    const agent = (ev.agent as string) ?? '系统'
    switch (type) {
      case 'agent_start': addTrace({ agent, action_type: 'start', content: ev.message as string }); break
      case 'think': addTrace({ agent, action_type: 'think', content: ev.content as string }); break
      case 'tool_call': addTrace({ agent, action_type: 'tool_call', content: JSON.stringify(ev.args ?? {}), tool_name: ev.tool as string }); break
      case 'tool_result': addTrace({ agent, action_type: 'tool_result', content: ev.preview as string, tool_name: ev.tool as string, latency_ms: ev.latency_ms as number }); break
      case 'section_draft': setDraft(ev.content as string); addTrace({ agent, action_type: 'output', content: `草稿完成，${ev.word_count} 字` }); break
      case 'agent_done': addTrace({ agent, action_type: 'output', content: ev.content as string }); break
      case 'error': addTrace({ agent, action_type: 'error', content: (ev.message ?? ev.content) as string }); break
    }
  }

  const saveRequirement = async () => {
    if (!project?.outline) return
    setSavingReq(true)
    try {
      const outline: Outline = {
        ...project.outline,
        sections: project.outline.sections.map(s => s.id === sid ? { ...s, requirement } : s),
      }
      await api.post(`/agent/projects/${projectId}/outline/confirm`, { outline })
      setProject(p => p ? { ...p, outline } : p)
      toast.success('写作要求已保存')
    } catch { toast.error('保存失败') }
    finally { setSavingReq(false) }
  }

  const runPipeline = async () => {
    if (running) return
    if (selectedKbs.length === 0) { toast.error('请至少选择一个检索知识库'); return }
    setTraces([]); setRunning(true)
    const ctrl = new AbortController(); abortRef.current = ctrl
    try {
      const resp = await fetch(`/api/agent/projects/${projectId}/sections/${sid}/write`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kb_ids: selectedKbs }), signal: ctrl.signal,
      })
      if (!resp.ok) { const err = await resp.json().catch(() => ({})); addTrace({ agent: '系统', action_type: 'error', content: err.detail || '写作失败' }); return }
      await consumeSse(resp, handleSse)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') addTrace({ agent: '系统', action_type: 'error', content: String(e) })
    } finally { setRunning(false); abortRef.current = null; await load() }
  }

  const toggleKb = (kid: number) => setSelectedKbs(prev => prev.includes(kid) ? prev.filter(x => x !== kid) : [...prev, kid])

  // 段落：按空行切分，供逐段精修
  const paragraphs = draft.split(/\n\s*\n/).filter(p => p.trim())
  const imageRefs = Array.from(draft.matchAll(/!\[([^\]]*)\]\(([^)]+)\)/g))
    .map(m => ({ alt: m[1] || '图片', url: m[2] }))
    .filter((img, idx, arr) => arr.findIndex(x => x.url === img.url) === idx)
  const draftStyle = { fontFamily: format.font_family, fontSize: `${format.font_size}px`, lineHeight: format.line_height }

  const saveDraft = async (content: string) => {
    await api.put(`/agent/projects/${projectId}/sections/${sid}/draft`, { content, format })
  }

  const replaceImage = async (targetUrl: string, file: File | undefined) => {
    if (!file) return
    setUploadingImage(targetUrl)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const { data } = await api.post(`/agent/projects/${projectId}/draft-images`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const next = draft.split(targetUrl).join(data.url)
      setDraft(next)
      await saveDraft(next)
      toast.success('图片已替换并保存')
    } catch {
      toast.error('图片替换失败')
    } finally {
      setUploadingImage(null)
    }
  }

  const applyRefine = async () => {
    if (refineIdx === null || !refineInstruction.trim()) return
    setRefining(true)
    try {
      const { data } = await api.post(`/agent/projects/${projectId}/sections/${sid}/refine`, {
        paragraph: paragraphs[refineIdx], instruction: refineInstruction,
      })
      const next = [...paragraphs]
      next[refineIdx] = data.refined
      const merged = next.join('\n\n')
      setDraft(merged)
      await saveDraft(merged)  // 精修即落库，避免重新生成时丢失
      setRefineIdx(null); setRefineInstruction('')
      toast.success('段落已精修并保存')
    } catch { toast.error('精修失败') }
    finally { setRefining(false) }
  }

  const saveEdit = async () => {
    setSavingDraft(true)
    try {
      await saveDraft(draft)
      setEditing(false)
      toast.success('草稿已保存')
    } catch { toast.error('保存失败') }
    finally { setSavingDraft(false) }
  }

  const saveFormatOnly = async () => {
    setSavingDraft(true)
    try {
      await saveDraft(draft)
      toast.success('格式已保存')
    } catch {
      toast.error('保存失败')
    } finally {
      setSavingDraft(false)
    }
  }

  const confirmSection = async () => {
    if (!draft.trim()) return
    setConfirming(true)
    try {
      await saveDraft(draft)
      await api.post(`/agent/projects/${projectId}/sections/${sid}/confirm`)
      toast.success('本章已确认，摘要已更新')
      await load()
    } catch {
      toast.error('确认失败')
    } finally {
      setConfirming(false)
    }
  }

  if (!project || !section) return <div className="flex h-full items-center justify-center text-sm text-slate-400">加载中…</div>

  const availableKbs = kbs.filter(k => projectKbIds(project).includes(k.id))

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* 顶栏 */}
      <div className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-5">
        <button onClick={() => navigate(`/writing/${projectId}`)} className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"><ArrowLeft className="h-5 w-5" /></button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold text-slate-800">{section.title}</h1>
          <p className="truncate text-xs text-slate-400">{project.title}{project.methodology ? ` · ${project.methodology}` : ''}</p>
        </div>
        {running ? (
          <Button size="sm" variant="danger" onClick={() => abortRef.current?.abort()}><Square className="h-3.5 w-3.5" fill="currentColor" />停止</Button>
        ) : (
          <Button size="sm" onClick={runPipeline}><Play className="h-3.5 w-3.5" />运行完整流程</Button>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* 左：配置 + 草稿 */}
        <div className="flex-1 overflow-y-auto bg-slate-50 p-6">
          <div className="mx-auto max-w-3xl space-y-5">
            {/* 关键要点 */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="mb-2 text-xs font-medium text-slate-400">本章关键要点</p>
              <div className="flex flex-wrap gap-1.5">
                {section.key_points.map((kp, i) => <span key={i} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{kp}</span>)}
              </div>
            </div>

            {/* 写作要求 */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-medium text-slate-400">详细写作要求（分几段、每段写什么）</p>
                <Button size="sm" variant="ghost" loading={savingReq} onClick={saveRequirement}><Save className="h-3.5 w-3.5" />保存</Button>
              </div>
              <Textarea rows={3} value={requirement} onChange={e => setRequirement(e.target.value)}
                placeholder="例：先交代研究背景与现状，再引出研究问题与本章贡献，最后说明本章结构，共分 3 段。" />
            </div>

            {/* 检索知识库 */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="mb-2 text-xs font-medium text-slate-400">本次检索知识库</p>
              {availableKbs.length === 0 ? (
                <p className="text-xs text-slate-400">该项目未绑定知识库，无法检索</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {availableKbs.map(k => {
                    const on = selectedKbs.includes(k.id)
                    return (
                      <button key={k.id} type="button" onClick={() => toggleKb(k.id)}
                        className={cn('flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-sm transition-colors',
                          on ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600 hover:border-slate-300')}>
                        <span className={cn('flex h-4 w-4 items-center justify-center rounded border', on ? 'border-indigo-500 bg-indigo-500 text-white' : 'border-slate-300')}>{on && <Check className="h-3 w-3" />}</span>
                        {k.name}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>

            {/* 草稿 */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-medium text-slate-400">章节草稿{draft && ` · ${draft.length} 字`}</p>
                {draft && (
                  editing ? (
                    <div className="flex items-center gap-1.5">
                      <Button size="sm" variant="ghost" onClick={() => { setEditing(false); load() }}>取消</Button>
                      <Button size="sm" loading={savingDraft} onClick={saveEdit}><Save className="h-3.5 w-3.5" />保存</Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-300">悬停段落可「精修」</span>
                      <Button size="sm" variant="outline" loading={confirming} onClick={confirmSection}><Check className="h-3.5 w-3.5" />确认并更新摘要</Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" />编辑全文</Button>
                    </div>
                  )
                )}
              </div>
              {draft && (
                <div className="mb-3 space-y-3 rounded-lg border border-slate-100 bg-slate-50/70 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Select value={format.font_family} onValueChange={v => setFormat(f => ({ ...f, font_family: v }))} options={FONT_OPTIONS} className="h-9 w-40" />
                    <Select value={String(format.font_size)} onValueChange={v => setFormat(f => ({ ...f, font_size: Number(v) }))} options={SIZE_OPTIONS} className="h-9 w-24" />
                    <Select value={String(format.line_height)} onValueChange={v => setFormat(f => ({ ...f, line_height: Number(v) }))} options={LINE_HEIGHT_OPTIONS} className="h-9 w-32" />
                    <Button size="sm" variant="ghost" loading={savingDraft} onClick={saveFormatOnly}><Save className="h-3.5 w-3.5" />保存格式</Button>
                  </div>
                  {imageRefs.length > 0 && (
                    <div className="space-y-2 border-t border-slate-200 pt-3">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
                        <ImageIcon className="h-3.5 w-3.5 text-indigo-500" />文中图片
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {imageRefs.map(img => (
                          <div key={img.url} className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-2">
                            <img src={img.url} alt={img.alt} className="h-10 w-12 rounded object-cover" />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-xs text-slate-500">{img.alt}</p>
                              <p className="truncate text-[11px] text-slate-300">{img.url.split('/').pop()}</p>
                            </div>
                            <label className="inline-flex h-8 cursor-pointer items-center gap-1 rounded-lg border border-slate-200 px-2 text-xs text-indigo-600 hover:bg-indigo-50">
                              <Upload className="h-3 w-3" />
                              {uploadingImage === img.url ? '上传中' : '替换'}
                              <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="hidden" onChange={e => replaceImage(img.url, e.target.files?.[0])} />
                            </label>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              {!draft ? (
                <div className="flex flex-col items-center gap-2 py-12 text-center text-slate-400">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-50 text-indigo-400"><Sparkles className="h-6 w-6" /></div>
                  <p className="text-sm">点击「运行完整流程」自动抽取关键词、跨库检索并生成草稿</p>
                </div>
              ) : editing ? (
                <Textarea rows={18} value={draft} onChange={e => setDraft(e.target.value)} style={draftStyle} className="text-sm" />
              ) : (
                <div className="space-y-2" style={draftStyle}>
                  {paragraphs.map((p, i) => (
                    <div key={i} className="group relative rounded-lg px-3 py-1 transition-colors hover:bg-slate-50">
                      <Markdown content={p} />
                      <button onClick={() => { setRefineIdx(i); setRefineInstruction('') }}
                        className="absolute right-2 top-2 flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-0.5 text-xs text-indigo-600 opacity-0 shadow-sm transition-opacity hover:bg-indigo-50 group-hover:opacity-100">
                        <Wand2 className="h-3 w-3" />精修
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 右：Trace */}
        <div className="flex w-80 shrink-0 flex-col overflow-hidden border-l border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <span className="flex items-center gap-1.5 text-sm font-medium text-slate-700"><Sparkles className="h-4 w-4 text-indigo-500" />Agent 活动</span>
            {running && <span className="flex items-center gap-1.5 text-xs text-indigo-500"><Spinner className="h-3 w-3" />写作中</span>}
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-2">
            {traces.length === 0 ? (
              <p className="py-8 text-center text-xs text-slate-400">运行后实时显示检索与写作过程</p>
            ) : traces.map((ev, i) => <TraceItem key={i} ev={ev} />)}
            <div ref={traceEndRef} />
          </div>
        </div>
      </div>

      {/* 段落精修弹窗 */}
      <Dialog open={refineIdx !== null} onOpenChange={(o) => { if (!o) setRefineIdx(null) }} title="精修段落" description="按指令重写该段落，保留已有引用，不编造新来源">
        {refineIdx !== null && (
          <div className="space-y-4">
            <div className="max-h-32 overflow-y-auto rounded-lg border border-slate-100 bg-slate-50/60 p-3 text-xs text-slate-500">{paragraphs[refineIdx]}</div>
            <Textarea rows={3} value={refineInstruction} onChange={e => setRefineInstruction(e.target.value)} placeholder="例：语言更精炼，补充与研究问题的衔接，去掉口语化表达" autoFocus />
            <div className="flex gap-3">
              <Button variant="secondary" className="flex-1" onClick={() => setRefineIdx(null)}>取消</Button>
              <Button className="flex-1" loading={refining} disabled={!refineInstruction.trim()} onClick={applyRefine}><Wand2 className="h-3.5 w-3.5" />精修</Button>
            </div>
          </div>
        )}
      </Dialog>
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
