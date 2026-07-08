import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * 全局 UI 偏好（持久化到 localStorage）。
 * 替代原先散落的 useStickyState，集中管理选中知识库、检索选项与侧栏状态。
 */
interface AppState {
  // 侧栏
  sidebarCollapsed: boolean
  toggleSidebar: () => void

  // 选中知识库（对话/检索共享）
  selectedKbId: number | null
  setSelectedKbId: (id: number | null) => void

  // 对话检索选项
  chatRewrite: boolean
  chatReranker: boolean
  setChatRewrite: (v: boolean) => void
  setChatReranker: (v: boolean) => void

  // RAG 检索页选项
  searchTopK: number
  searchRewrite: boolean
  searchHyde: boolean
  searchReranker: boolean
  setSearch: (patch: Partial<Pick<AppState, 'searchTopK' | 'searchRewrite' | 'searchHyde' | 'searchReranker'>>) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set(s => ({ sidebarCollapsed: !s.sidebarCollapsed })),

      selectedKbId: null,
      setSelectedKbId: (id) => set({ selectedKbId: id }),

      chatRewrite: true,
      chatReranker: false,
      setChatRewrite: (v) => set({ chatRewrite: v }),
      setChatReranker: (v) => set({ chatReranker: v }),

      searchTopK: 10,
      searchRewrite: true,
      searchHyde: false,
      searchReranker: false,
      setSearch: (patch) => set(patch),
    }),
    { name: 'paper-rag-prefs' },
  ),
)
