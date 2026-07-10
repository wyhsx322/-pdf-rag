import { createContext, useContext, useState, useCallback, type ReactNode, type Dispatch, type SetStateAction } from 'react'
import type { Conversation } from '../../entities/chat/model'
import {
  listConversations,
  getConversation,
  deleteConversation as deleteConvApi,
  createConversation,
  appendMessages,
  type LongTermMemoryCandidate,
  type LongTermMemoryUsed,
} from './api'

// ── 展示用消息类型 ──

export interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  sources: string[]
  figures: Array<{
    chunk_id: string
    source: string
    image_file: string
    caption: string
    page: number | null
    figure_type: string
  }>
  memoryCandidate?: LongTermMemoryCandidate | null
  memoryUsed?: LongTermMemoryUsed[]
  isStreaming: boolean
}

// ── Context ──

interface ChatContextValue {
  // 对话列表
  conversations: Conversation[]
  loadConversations: (kbId: number) => Promise<void>

  // 当前对话
  currentConvId: number | null
  messages: DisplayMessage[]
  loading: boolean

  // 操作
  selectConversation: (convId: number) => Promise<void>
  newConversation: () => void
  deleteConversation: (convId: number) => Promise<void>
  saveExchange: (kbId: number, userContent: string, assistantContent: string, sources: string[]) => Promise<void>

  // 流式消息更新
  setMessages: Dispatch<SetStateAction<DisplayMessage[]>>
  setLoading: (v: boolean) => void
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConvId, setCurrentConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [loading, setLoading] = useState(false)

  const loadConversations = useCallback(async (kbId: number) => {
    try {
      const data = await listConversations(kbId)
      setConversations(data)
    } catch {
      // 静默失败
    }
  }, [])

  const selectConversation = useCallback(async (convId: number) => {
    try {
      const detail = await getConversation(convId)
      const msgs: DisplayMessage[] = detail.messages.map(m => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        sources: JSON.parse(m.sources || '[]'),
        figures: [],
        memoryCandidate: null,
        memoryUsed: [],
        isStreaming: false,
      }))
      setMessages(msgs)
      setCurrentConvId(convId)
    } catch {
      // 静默失败
    }
  }, [])

  const newConversation = useCallback(() => {
    setMessages([])
    setCurrentConvId(null)
    setLoading(false)
  }, [])

  const deleteConversation = useCallback(async (convId: number) => {
    try {
      await deleteConvApi(convId)
      setConversations(prev => prev.filter(c => c.id !== convId))
      if (currentConvId === convId) {
        newConversation()
      }
    } catch {
      // 静默失败
    }
  }, [currentConvId, newConversation])

  const saveExchange = useCallback(async (
    kbId: number,
    userContent: string,
    assistantContent: string,
    sources: string[],
  ) => {
    const messages = [
      { role: 'user', content: userContent, sources: [] as string[] },
      { role: 'assistant', content: assistantContent, sources },
    ]

    try {
      if (currentConvId) {
        await appendMessages(currentConvId, messages)
        // 更新列表中的 updated_at 和 message_count
        setConversations(prev =>
          prev.map(c =>
            c.id === currentConvId
              ? { ...c, message_count: c.message_count + 2, updated_at: new Date().toISOString() }
              : c,
          ),
        )
      } else {
        // 创建新对话，标题取用户问题前 30 字
        const title = userContent.slice(0, 30)
        const conv = await createConversation(kbId, title)
        setCurrentConvId(conv.id)
        await appendMessages(conv.id, messages)
        // 刷新对话列表
        await loadConversations(kbId)
      }
    } catch {
      // 保存失败不影响前端展示
    }
  }, [currentConvId, loadConversations])

  return (
    <ChatContext.Provider
      value={{
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
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) {
    throw new Error('useChatContext must be used within ChatProvider')
  }
  return ctx
}
