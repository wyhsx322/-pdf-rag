import type { ReactNode } from 'react'
import Sidebar from './Sidebar'

/** 应用骨架：左侧栏 + 主内容区（浅色）。各页面自行管理内部滚动与留白。 */
export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">{children}</main>
    </div>
  )
}
