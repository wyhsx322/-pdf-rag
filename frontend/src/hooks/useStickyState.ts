import { useState, useEffect, useCallback, useRef } from 'react'

/** 从 sessionStorage 恢复状态，写入时自动同步持久化。 */
export function useStickyState<T>(
  key: string,
  defaultValue: T,
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    try {
      const stored = sessionStorage.getItem(key)
      if (stored !== null) {
        const parsed = JSON.parse(stored)
        return deserialize(parsed, defaultValue) as T
      }
    } catch { /* 解析失败，回退默认值 */ }
    return defaultValue
  })

  // 用 ref 跟踪首次挂载，避免首次同步写回相同值
  const mounted = useRef(false)
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true
      return
    }
    try {
      sessionStorage.setItem(key, JSON.stringify(serialize(state)))
    } catch { /* quota 满或序列化失败，静默忽略 */ }
  }, [key, state])

  return [state, setState]
}

// ── 序列化辅助 ────────────────────────────────────────────────

function serialize(value: unknown): unknown {
  if (value instanceof Set) {
    return { __t: 'Set', v: [...value] }
  }
  if (value instanceof Map) {
    return { __t: 'Map', v: [...value] }
  }
  return value
}

function deserialize(parsed: unknown, fallback: unknown): unknown {
  if (
    parsed &&
    typeof parsed === 'object' &&
    '__t' in parsed &&
    'v' in parsed
  ) {
    const obj = parsed as { __t: string; v: unknown }
    if (obj.__t === 'Set' && Array.isArray(obj.v)) {
      return new Set(obj.v)
    }
    if (obj.__t === 'Map' && Array.isArray(obj.v)) {
      return new Map(obj.v as [unknown, unknown][])
    }
  }
  // 若默认值是 Set/Map，但从 storage 读到的不是，回退默认值
  if (fallback instanceof Set || fallback instanceof Map) {
    if (parsed === null || parsed === undefined) return fallback
    if (Array.isArray(parsed) && fallback instanceof Set) {
      return new Set(parsed)
    }
    if (Array.isArray(parsed) && fallback instanceof Map) {
      return new Map(parsed as [unknown, unknown][])
    }
  }
  return parsed
}
