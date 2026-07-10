import { api } from '../../shared/api/http'
import type {
  KnowledgeBase, KnowledgeBaseDetail, Document, ChunkPreviewRequest,
  ChunkPreviewResponse, ChunkExecuteRequest, MessageResponse, KBType,
} from './model'

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
