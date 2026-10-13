/** SSE 事件 / 消息 parts 类型：对齐后端 api/v1/agent.py 的 v2 流式协议。
 *  事件序列 = 有序 tool start/end（agent 执行流程）+ 最终 answer + done/error。
 */

/** 并行分支（诊断意图 id + 中文名），仅 Send 分支内的节点携带 */
export interface BranchInfo {
  branch?: string
  branch_name?: string
}

export interface ToolStartEvent extends BranchInfo {
  type: 'tool'
  node: string
  name: string
  status: 'start'
}

export interface ToolEndEvent extends BranchInfo {
  type: 'tool'
  node: string
  name: string
  status: 'end'
  result?: unknown
}

export type ToolEvent = ToolStartEvent | ToolEndEvent

export interface AnswerSop {
  summary?: string
  steps?: { title?: string; detail?: string }[]
  parts?: { part_no?: string; name?: string; qty?: number }[]
  safety?: string[]
  no_data_found?: boolean
  [key: string]: unknown
}

/** 图谱诊断结果（query_graph 的 alarm_reasoning 输出，供 GraphPanel 渲染） */
export interface GraphAlarm {
  code?: string
  title?: string
  subsystem?: string
  page?: string | number
  causes?: string[]
  sops?: string[]
  direct_sops?: string[]
  cause_chain?: { text?: string; sops?: string[] }[]
  similar?: { method?: string; count?: number; items?: { code?: string; title?: string; page?: string }[] }
  [key: string]: unknown
}

export interface GraphResult {
  intent?: string
  brand?: string
  alarm_code?: string
  anchors?: { brand?: string; code?: string; score?: number | null; source?: string }[]
  results?: GraphAlarm[]
}

export interface ConfirmEvent {
  type: 'confirm'
  prompt: string
  options?: string[]
  node?: string
  /** 人工确认前要审阅的已生成 SOP（可能多分支多个） */
  sops?: AnswerSop[]
}

/** 手册检索召回并带回的图片（asset_url 为 OSS 签名临时 URL） */
export interface ManualImage {
  asset_url: string
  content?: string
  title?: string
  section?: string
  page?: string | number | null
}

/** 手册检索召回并带回的文本片段（参考材料，折叠展示） */
export interface ManualChunk {
  section?: string
  page?: string | number | null
  brand?: string
  score?: number
  content?: string
}

export interface AnswerEvent {
  type: 'answer'
  text: string
  sop?: AnswerSop | null
  sops?: AnswerSop[]
  graphs?: GraphResult[]
  manual_images?: ManualImage[]
  manual_chunks?: ManualChunk[]
  work_order?: { ok?: boolean; work_order_no?: string; priority?: string; note?: string }
}

/** narrate 节点逐 token 叙述：追加到当前助手消息的最后一个文本 part */
export interface AnswerDeltaEvent {
  type: 'answer_delta'
  text: string
}

export interface DoneEvent {
  type: 'done'
}

export interface ErrorEvent {
  type: 'error'
  message: string
}

export type SSEEvent = ToolEvent | AnswerEvent | AnswerDeltaEvent | ConfirmEvent | DoneEvent | ErrorEvent

/** 助手消息 = 有序 parts（工具卡片与文本按执行顺序交错） */
export type MessagePart =
  | { kind: 'text'; content: string }
  | {
      kind: 'tool'
      key: string
      node: string
      name: string
      status: 'running' | 'done'
      result?: unknown
      branch?: string
      branch_name?: string
    }
  | { kind: 'sop'; key: string; sop: AnswerSop }
  | { kind: 'manual_images'; key: string; images: ManualImage[] }
  | { kind: 'manual_chunks'; key: string; chunks: ManualChunk[] }

export type ToolPart = Extract<MessagePart, { kind: 'tool' }>

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  parts: MessagePart[]
}
