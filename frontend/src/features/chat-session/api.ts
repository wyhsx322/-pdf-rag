import { api } from '../../shared/api/http'
import type { Conversation, ConversationDetail } from '../../entities/chat/model'

// ── 问答对话（SSE 流式） ──

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface LongTermMemoryCandidate {
  id: number
  kb_id: number | null
  project_id: number | null
  conversation_id: number | null
  category: string
  content: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  updated_at: string
}

export interface LongTermMemoryUsed {
  id: number
  category: string
  content: string
  score: number
}

export function chatQA(
  kbId: number,
  question: string,
  history: ChatMessage[],
  topK: number,
  useReranker: boolean,
  useRewrite: boolean,
  conversationId: number | null,
  onText: (text: string) => void,
  onSource: (source: string) => void,
  onDone: (fullAnswer: string, sources: string[], figures: Array<{
    chunk_id: string; source: string; image_file: string;
    caption: string; page: number | null; figure_type: string;
  }>, memoryUsed?: LongTermMemoryUsed[], memoryCandidate?: LongTermMemoryCandidate | null) => void,
  onError: (error: string) => void,
  onMemoryCandidate?: (candidate: LongTermMemoryCandidate) => void,
  onMemoryUsed?: (memories: LongTermMemoryUsed[]) => void,
  onShortMemorySummary?: (summary: string, estimatedTokens: number) => void,
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
      conversation_id: conversationId,
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
            } else if (parsed.type === 'memory_used') {
              onMemoryUsed?.(parsed.memories || [])
            } else if (parsed.type === 'memory_candidate') {
              if (parsed.candidate) onMemoryCandidate?.(parsed.candidate)
            } else if (parsed.type === 'short_memory_summary') {
              onShortMemorySummary?.(parsed.summary || '', parsed.estimated_tokens || 0)
            } else if (parsed.type === 'done') {
              onDone(
                parsed.full_answer || '',
                parsed.sources || [],
                parsed.figures || [],
                parsed.memory_used || [],
                parsed.memory_candidate || null,
              )
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

export async function approveLongTermMemoryCandidate(id: number): Promise<LongTermMemoryCandidate> {
  const { data } = await api.post(`/memory/long-term/candidates/${id}/approve`)
  return data
}

export async function rejectLongTermMemoryCandidate(id: number): Promise<LongTermMemoryCandidate> {
  const { data } = await api.post(`/memory/long-term/candidates/${id}/reject`)
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
