import type { ReactNode } from 'react'
import Sidebar from './Sidebar'

/** 应用骨架：左侧栏 + 主内容区（浅色）。各页面自行管理内部滚动与留白。 */
export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[radial-gradient(circle_at_20%_0%,rgba(79,70,229,0.12),transparent_32%),linear-gradient(135deg,#f8fafc_0%,#eef4ff_48%,#f7fbff_100%)]">
      <Sidebar />
      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-indigo-300/70 to-transparent" />
        {children}
      </main>
    </div>
  )
}
