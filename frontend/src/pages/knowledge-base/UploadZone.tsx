import { useCallback, useRef, useState } from 'react'
import { UploadCloud, Loader2 } from 'lucide-react'
import { cn } from '../../shared/lib/cn'

interface Props {
  onUpload: (files: File[]) => Promise<void>
  uploading: boolean
}

export default function UploadZone({ onUpload, uploading }: Props) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'))
    if (files.length) onUpload(files)
  }, [onUpload])

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={e => { e.preventDefault(); setDragging(false) }}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      className={cn(
        'cursor-pointer rounded-[26px] border-2 border-dashed p-10 text-center transition-all',
        dragging ? 'border-indigo-400 bg-indigo-50/60' : 'border-white/80 bg-white/65 shadow-soft hover:border-indigo-300 hover:bg-white/90',
        uploading && 'pointer-events-none opacity-60',
      )}
    >
      <input ref={inputRef} type="file" accept=".pdf" multiple className="hidden"
        onChange={e => { const f = Array.from(e.target.files || []); if (f.length) { onUpload(f); e.target.value = '' } }} />
      <div className="flex flex-col items-center gap-2.5">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-950 text-cyan-200 shadow-glow">
          {uploading ? <Loader2 className="h-6 w-6 animate-spin" /> : <UploadCloud className="h-6 w-6" />}
        </div>
        {uploading ? (
          <p className="text-sm text-slate-500">正在上传…</p>
        ) : (
          <div>
            <p className="text-sm font-medium text-slate-700">拖拽 PDF 到此处，或点击上传</p>
            <p className="mt-0.5 text-xs text-slate-400">支持批量上传，仅限 PDF 格式</p>
          </div>
        )}
      </div>
    </div>
  )
}
