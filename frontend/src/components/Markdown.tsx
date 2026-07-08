import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeHighlight from 'rehype-highlight'
import { cn } from '../lib/cn'

/**
 * 统一 Markdown 渲染：GFM 表格/任务列表 + KaTeX 数学公式 + 代码高亮。
 * 用于对话回答与论文章节草稿。样式见 index.css 的 .prose-chat。
 */
function MarkdownImpl({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn('prose-chat max-w-none', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, [rehypeHighlight, { detect: true, ignoreMissing: true }]]}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default memo(MarkdownImpl)
