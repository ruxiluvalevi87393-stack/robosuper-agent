import { useAuthStore } from '../store/auth'
import type { SSEEvent } from '../pages/Workspace/types'

/**
 * SSE 流式对话：POST /api/v1/agent/chat（需 Bearer），用 fetch 流式读取逐行解析 data: 事件。
 * 不用 EventSource —— 它只支持 GET 且无法带自定义请求头。
 * resumeInput 非空时走 resume 模式：从人工确认断点续跑（Command(resume=...))。
 */
export async function chatStream(
  sessionId: string,
  query: string,
  onEvent: (ev: SSEEvent) => void,
  signal?: AbortSignal,
  resumeInput?: string,
): Promise<void> {
  const token = useAuthStore.getState().token
  const resp = await fetch('/api/v1/agent/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ session_id: sessionId, query, resume_input: resumeInput }),
    signal,
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`对话请求失败：HTTP ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 事件以空行分隔
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      for (const line of block.split('\n')) {
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (!payload || payload === '[DONE]') continue
        try {
          onEvent(JSON.parse(payload) as SSEEvent)
        } catch {
          // 忽略无法解析的行，避免中断整个流
        }
      }
    }
  }
}
