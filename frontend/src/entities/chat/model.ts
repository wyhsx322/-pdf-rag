// ── 问答对话 ──

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// ── 历史对话 ──

export interface Conversation {
  id: number
  kb_id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationMessage {
  id: number
  conversation_id: number
  role: 'user' | 'assistant'
  content: string
  sources: string  // JSON 字符串数组
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[]
}
