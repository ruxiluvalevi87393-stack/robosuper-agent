import { useCallback, useRef, useState } from 'react'
import { chatStream } from '../api/agent'
import type { ChatMessage, ConfirmEvent, GraphResult, SSEEvent } from '../pages/Workspace/types'

let seq = 0
const nextId = () => `k${Date.now()}-${seq++}`

export type ChatStatus = 'idle' | 'running' | 'waiting' | 'done' | 'error'

/**
 * 把后端 SSE v2 事件流（有序 tool start/end + confirm + answer）归一化为：
 * - messages：助手消息 = 有序 parts（工具卡片实时插入，最终文本追加）
 * - confirm：人工确认卡（interrupt 触发，resume 续跑）
 * - graphs：图谱诊断数据（供 GraphPanel）
 * - status / error / abort
 */
export function useChatSse() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<Omit<ConfirmEvent, 'type'> | null>(null)
  const [graphs, setGraphs] = useState<GraphResult[]>([])
  const sessionRef = useRef<string>(`ws_${Date.now()}`)
  const abortRef = useRef<AbortController | null>(null)
  const asstIdRef = useRef<string | null>(null)
  const deltaStreamedRef = useRef(false)

  /** 当前助手消息（首个 tool 事件到达时创建）；id 在回调体生成，updater 保持纯净 */
  const ensureAssistant = useCallback(() => {
    if (!asstIdRef.current) {
      const id = nextId()
      asstIdRef.current = id
      setMessages((prev) => (prev.some((m) => m.id === id) ? prev : [...prev, { id, role: 'assistant', parts: [] }]))
    }
  }, [])

  const markRunningDone = useCallback(() => {
    setMessages((prev) =>
      prev.map((m) =>
        m.role === 'assistant'
          ? { ...m, parts: m.parts.map((p) => (p.kind === 'tool' ? { ...p, status: 'done' as const } : p)) }
          : m,
      ),
    )
  }, [])

  const handleEvent = useCallback(
    (ev: SSEEvent) => {
      switch (ev.type) {
        case 'tool': {
          ensureAssistant()
          if (ev.status === 'start') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === asstIdRef.current
                  ? {
                      ...m,
                      parts: [
                        ...m.parts,
                        {
                          kind: 'tool',
                          key: nextId(),
                          node: ev.node,
                          name: ev.name,
                          status: 'running',
                          branch: ev.branch,
                          branch_name: ev.branch_name,
                        },
                      ],
                    }
                  : m,
              ),
            )
          } else {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === asstIdRef.current
                  ? {
                      ...m,
                      parts: m.parts.map((p) =>
                        // 并行分支存在同名节点（如两个 query_graph 同时运行），必须按分支匹配
                        p.kind === 'tool' && p.node === ev.node && p.status === 'running' && (p.branch ?? null) === (ev.branch ?? null)
                          ? {
                              ...p,
                              status: 'done' as const,
                              result: ev.result,
                              branch: p.branch ?? ev.branch,
                              branch_name: p.branch_name ?? ev.branch_name,
                            }
                          : p,
                      ),
                    }
                  : m,
              ),
            )
          }
          break
        }
        case 'answer_delta': {
          // 真流式叙述：追加到当前助手消息的最后一个 text part
          ensureAssistant()
          deltaStreamedRef.current = true
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== asstIdRef.current) return m
              const parts = [...m.parts]
              const last = parts[parts.length - 1]
              if (last && last.kind === 'text') {
                parts[parts.length - 1] = { ...last, content: last.content + ev.text }
              } else {
                parts.push({ kind: 'text', content: ev.text })
              }
              return { ...m, parts }
            }),
          )
          break
        }
        case 'answer': {
          ensureAssistant()
          if (ev.graphs && ev.graphs.length > 0) setGraphs(ev.graphs)
          setMessages((prev) =>
            prev.map((m) =>
              m.id === asstIdRef.current
                ? {
                    ...m,
                    parts: [
                      ...m.parts,
                      // 已流式叙述时文本已逐 token 追加，不重复；direct_answer 等未流式路径仍整段追加
                      ...(deltaStreamedRef.current ? [] : [{ kind: 'text' as const, content: ev.text }]),
                      ...(ev.sops && ev.sops.length > 0
                        ? ev.sops.map((sop) => ({ kind: 'sop' as const, key: nextId(), sop }))
                        : ev.sop
                          ? [{ kind: 'sop' as const, key: nextId(), sop: ev.sop }]
                          : []),
                      ...(ev.manual_images && ev.manual_images.length > 0
                        ? [{ kind: 'manual_images' as const, key: nextId(), images: ev.manual_images }]
                        : []),
                      ...(ev.manual_chunks && ev.manual_chunks.length > 0
                        ? [{ kind: 'manual_chunks' as const, key: nextId(), chunks: ev.manual_chunks }]
                        : []),
                    ],
                  }
                : m,
            ),
          )
          markRunningDone()
          break
        }
        case 'confirm': {
          // interrupt 到达：等待人工确认，resume 后继续
          setConfirm({ prompt: ev.prompt, options: ev.options ?? [], node: ev.node, sops: ev.sops ?? [] })
          setStatus('waiting')
          break
        }
        case 'error':
          setError(ev.message || '未知错误')
          setStatus('error')
          break
        case 'done':
          markRunningDone()
          setStatus('done')
          break
      }
    },
    [ensureAssistant, markRunningDone],
  )

  /** 人工确认：调用 resume 模式从断点续跑 */
  const confirmDecision = useCallback(
    async (input: string) => {
      if (status !== 'waiting') return
      setConfirm(null)
      setStatus('running')
      const ac = new AbortController()
      abortRef.current = ac
      try {
        await chatStream(sessionRef.current, '', handleEvent, ac.signal, input)
      } catch (e) {
        if ((e as Error).name === 'AbortError') {
          markRunningDone()
          setStatus('done')
          return
        }
        setError((e as Error).message || '请求失败')
        setStatus('error')
      }
    },
    [status, handleEvent, markRunningDone],
  )

  const send = useCallback(
    async (query: string) => {
      const q = query.trim()
      if (!q || status === 'running' || status === 'waiting') return
      setMessages((prev) => [...prev, { id: nextId(), role: 'user', parts: [{ kind: 'text', content: q }] }])
      setError(null)
      setConfirm(null)
      setGraphs([])
      asstIdRef.current = null
      deltaStreamedRef.current = false
      setStatus('running')

      const ac = new AbortController()
      abortRef.current = ac
      try {
        await chatStream(sessionRef.current, q, handleEvent, ac.signal)
      } catch (e) {
        if ((e as Error).name === 'AbortError') {
          markRunningDone()
          setStatus('done')
          return
        }
        setError((e as Error).message || '请求失败')
        setStatus('error')
      }
    },
    [status, handleEvent, markRunningDone],
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    sessionRef.current = `ws_${Date.now()}`
    asstIdRef.current = null
    deltaStreamedRef.current = false
    setMessages([])
    setConfirm(null)
    setGraphs([])
    setStatus('idle')
    setError(null)
  }, [])

  return { messages, status, error, confirm, graphs, send, confirmDecision, abort, reset }
}
