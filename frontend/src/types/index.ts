// 知识库类型
export type KBType = 'work' | 'study' | 'personal'

export interface KnowledgeBase {
  id: number
  name: string
  type: KBType
  description: string
  created_at: string
  document_count: number
}

export interface KnowledgeBaseDetail extends KnowledgeBase {
  documents: Document[]
}

// 文档类型
export type DocumentStatus = 'uploaded' | 'parsed' | 'chunked' | 'indexed' | 'error'

export interface Document {
  id: number
  kb_id: number
  filename: string
  original_name: string
  file_size: number
  status: DocumentStatus
  page_count: number | null
  created_at: string
}

// 切片相关类型
export type ChunkMethod = 'recursive' | 'sentence' | 'paragraph' | 'fixed'

export interface ChunkPreviewRequest {
  text: string
  method: ChunkMethod
  chunk_size: number
  chunk_overlap: number
  separators: string[]
  preserve_images: boolean
  preserve_tables: boolean
}

export interface ChunkResult {
  chunk_id: string
  page: number
  text: string
  text_length: number
  has_figure: boolean
}

export interface ChunkPreviewResponse {
  total_chunks: number
  chunks: ChunkResult[]
  avg_chunk_size: number
}

export interface ChunkExecuteRequest {
  method: ChunkMethod
  chunk_size: number
  chunk_overlap: number
  separators: string[]
  preserve_images: boolean
  preserve_tables: boolean
}

// 通用类型
export interface MessageResponse {
  message: string
  success: boolean
}

// KB 类型标签映射
export const KB_TYPE_LABELS: Record<KBType, string> = {
  work: '工作',
  study: '学习',
  personal: '个人',
}

export const KB_TYPE_ICONS: Record<KBType, string> = {
  work: '💼',
  study: '📚',
  personal: '👤',
}

// 文档状态标签映射
export const DOC_STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: '已上传',
  parsed: '已解析',
  chunked: '已切片',
  indexed: '已入库',
  error: '异常',
}

export const DOC_STATUS_COLORS: Record<DocumentStatus, string> = {
  uploaded: 'bg-slate-100 text-slate-700',
  parsed: 'bg-blue-100 text-blue-700',
  chunked: 'bg-amber-100 text-amber-700',
  indexed: 'bg-emerald-100 text-emerald-700',
  error: 'bg-red-100 text-red-700',
}

// 切片方式标签映射
export const CHUNK_METHOD_LABELS: Record<ChunkMethod, string> = {
  recursive: '递归分割',
  sentence: '按句子',
  paragraph: '按段落',
  fixed: '固定大小',
}

// 默认分隔符
export const DEFAULT_SEPARATORS: Record<ChunkMethod, string[]> = {
  recursive: ['\n\n', '\n', '。', '.', '！', '？', '；', ';', ' ', ''],
  sentence: ['。', '.', '！', '？', '；', ';', '\n\n', '\n'],
  paragraph: ['\n\n', '\n'],
  fixed: [''],
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
