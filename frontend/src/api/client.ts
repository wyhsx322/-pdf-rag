import axios from 'axios'
import type {
  KnowledgeBase,
  KnowledgeBaseDetail,
  Document,
  ChunkPreviewRequest,
  ChunkPreviewResponse,
  ChunkExecuteRequest,
  MessageResponse,
  KBType,
  Conversation,
  ConversationDetail,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 流水线处理可能需要较长时间
})

// ── 知识库 ──

export async function listKBs(): Promise<KnowledgeBase[]> {
  const { data } = await api.get('/kb')
  return data
}

export async function createKB(name: string, type: KBType, description: string): Promise<KnowledgeBase> {
  const { data } = await api.post('/kb', { name, type, description })
  return data
}

export async function getKB(id: number): Promise<KnowledgeBaseDetail> {
  const { data } = await api.get(`/kb/${id}`)
  return data
}

export async function deleteKB(id: number): Promise<MessageResponse> {
  const { data } = await api.delete(`/kb/${id}`)
  return data
}

// ── 文档 ──

export async function listDocuments(kbId: number, search?: string, status?: string): Promise<Document[]> {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (status) params.set('status', status)
  const query = params.toString()
  const { data } = await api.get(`/kb/${kbId}/documents${query ? '?' + query : ''}`)
  return data
}

export async function uploadDocuments(kbId: number, files: File[]): Promise<Document[]> {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  const { data } = await api.post(`/kb/${kbId}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteDocument(docId: number): Promise<MessageResponse> {
  const { data } = await api.delete(`/documents/${docId}`)
  return data
}

export async function batchImportDocuments(kbId: number, sourceDir: string = ''): Promise<Document[]> {
  const { data } = await api.post(`/kb/${kbId}/batch-import`, { source_dir: sourceDir })
  return data
}

export async function processDocument(docId: number): Promise<MessageResponse> {
  const { data } = await api.post(`/documents/${docId}/process`)
  return data
}

// ── 切片 ──

export async function previewChunking(req: ChunkPreviewRequest): Promise<ChunkPreviewResponse> {
  const { data } = await api.post('/chunk/preview', req)
  return data
}

export async function executeChunking(docId: number, req: ChunkExecuteRequest): Promise<MessageResponse> {
  const { data } = await api.post(`/documents/${docId}/chunk`, req)
  return data
}

// ── 混合检索 ──

export interface SearchResultItem {
  rank: number
  chunk_id: string
  text: string
  page: number | null
  source: string
  vector_score: number
  bm25_score: number
  rrf_score: number
  rerank_score: number | null
  is_figure: boolean
  figure_type: string | null
  caption: string | null
  image_file: string | null
  image_path: string | null
}

export interface SearchResponse {
  query: string
  total_results: number
  search_mode: string
  results: SearchResultItem[]
  elapsed_seconds: number
}

export async function hybridSearch(
  kbId: number,
  query: string,
  topK: number = 10,
  useReranker: boolean = false,
  useRewrite: boolean = true,
  useHyde: boolean = false,
): Promise<SearchResponse> {
  const { data } = await api.post('/search', {
    kb_id: kbId,
    query,
    top_k: topK,
    use_reranker: useReranker,
    use_rewrite: useRewrite,
    use_hyde: useHyde,
  })
  return data
}

// ── 问答对话（SSE 流式） ──

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export function chatQA(
  kbId: number,
  question: string,
  history: ChatMessage[],
  topK: number,
  useReranker: boolean,
  useRewrite: boolean,
  onText: (text: string) => void,
  onSource: (source: string) => void,
  onDone: (fullAnswer: string, sources: string[], figures: Array<{
    chunk_id: string; source: string; image_file: string;
    caption: string; page: number | null; figure_type: string;
  }>) => void,
  onError: (error: string) => void,
): AbortController {
  const controller = new AbortController()

  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      kb_id: kbId,
      question,
      history,
      top_k: topK,
      use_reranker: useReranker,
      use_rewrite: useRewrite,
    }),
    signal: controller.signal,
  }).then(async (response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '请求失败' }))
      onError(err.detail || `HTTP ${response.status}`)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError('无法读取响应流')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const parsed = JSON.parse(line.slice(6))
            if (parsed.type === 'text') {
              onText(parsed.content)
            } else if (parsed.type === 'source') {
              onSource(parsed.content)
            } else if (parsed.type === 'done') {
              onDone(parsed.full_answer || '', parsed.sources || [], parsed.figures || [])
            } else if (parsed.type === 'error') {
              onError(parsed.content)
            }
          } catch {
            // 跳过解析失败的行
          }
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      onError(err.message || '网络请求失败')
    }
  })

  return controller
}

// ── 批量处理（SSE 流式进度） ──

export interface BatchProgressEvent {
  doc_id: number
  original_name: string
  status: 'processing' | 'done' | 'error'
  message: string
}

export function batchProcessDocuments(
  kbId: number,
  docIds: number[],
  onProgress: (event: BatchProgressEvent) => void,
  onAllDone: (total: number) => void,
  onError: (error: string) => void,
): AbortController {
  const controller = new AbortController()

  fetch(`/api/kb/${kbId}/batch-process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_ids: docIds }),
    signal: controller.signal,
  }).then(async (response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '请求失败' }))
      onError(err.detail || `HTTP ${response.status}`)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError('无法读取响应流')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const parsed = JSON.parse(line.slice(6))
            if (parsed.type === 'all_done') {
              onAllDone(parsed.total || 0)
            } else {
              onProgress(parsed)
            }
          } catch {
            // 跳过解析失败的行
          }
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      onError(err.message || '网络请求失败')
    }
  })

  return controller
}

// ── 向量库操作 ──

export interface VectorStats {
  doc_id: number
  original_name: string
  status: string
  collection_name: string
  collection_exists: boolean
  vector_count: number
}

export async function getVectorStats(docId: number): Promise<VectorStats> {
  const { data } = await api.get(`/documents/${docId}/vector-stats`)
  return data
}

export async function deleteVectors(docId: number): Promise<MessageResponse> {
  const { data } = await api.delete(`/documents/${docId}/vectors`)
  return data
}

export async function reindexDocument(docId: number): Promise<MessageResponse> {
  const { data } = await api.post(`/documents/${docId}/reindex`)
  return data
}

// ── 历史对话 ──

export async function listConversations(kbId: number): Promise<Conversation[]> {
  const { data } = await api.get('/conversations', { params: { kb_id: kbId } })
  return data
}

export async function createConversation(kbId: number, title: string = ''): Promise<Conversation> {
  const { data } = await api.post('/conversations', { kb_id: kbId, title })
  return data
}

export async function getConversation(convId: number): Promise<ConversationDetail> {
  const { data } = await api.get(`/conversations/${convId}`)
  return data
}

export async function deleteConversation(convId: number): Promise<void> {
  await api.delete(`/conversations/${convId}`)
}

export async function appendMessages(
  convId: number,
  messages: { role: string; content: string; sources: string[] }[],
): Promise<void> {
  await api.post(`/conversations/${convId}/messages`, { messages })
}