import { useEffect, useRef, useState } from 'react'
import { Button, Collapse, Image, Input } from 'antd'
import {
  CheckCircleFilled,
  DownOutlined,
  FileTextOutlined,
  LoadingOutlined,
  PictureOutlined,
  RobotOutlined,
  SendOutlined,
  ToolOutlined,
  UpOutlined,
  UserOutlined,
} from '@ant-design/icons'
import type { ChatStatus } from '../../hooks/useChatSse'
import ConfirmCard from './ConfirmCard'
import SopSummary from './SopSummary'
import type { ChatMessage, ConfirmEvent, ManualChunk, ManualImage, MessagePart, ToolPart } from './types'

interface Props {
  messages: ChatMessage[]
  status: ChatStatus
  confirm: Omit<ConfirmEvent, 'type'> | null
  onConfirm: (input: string) => void
  onSend: (query: string) => void
  onAbort: () => void
}

const SUGGESTIONS = [
  'FANUC SRVO-050 碰撞报警怎么处理',
  'FANUC 伺服轴抖动是什么原因？碰撞报警怎么处理？程序中断如何排查？',
  'ABB 程序中断如何排查',
  'KUKA 机器人报警怎么复位',
]

/** 主对话面板：欢迎建议 + 有序消息流（工具卡片实时插入）+ 人工确认卡 + 输入框/停止。 */
export default function ChatPanel({ messages, status, confirm, onConfirm, onSend, onAbort }: Props) {
  const [text, setText] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const running = status === 'running'
  const waiting = status === 'waiting'
  const submit = () => {
    const q = text.trim()
    if (!q || running) return
    setText('')
    onSend(q)
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#1f1f1f',
        border: '1px solid #303030',
        borderRadius: 4,
        minHeight: 0,
      }}
    >
      <div style={{ flex: 1, overflowY: 'auto', padding: 16, minHeight: 0 }}>
        {messages.length === 0 ? (
          <Welcome onPick={onSend} />
        ) : (
          messages.map((m) => <MessageBubble key={m.id} msg={m} />)
        )}
        <div ref={bottomRef} />
      </div>
      {waiting && <ConfirmCard confirm={confirm} busy={false} onDecision={onConfirm} />}
      <div style={{ padding: 12, borderTop: '1px solid #303030', display: 'flex', gap: 8 }}>
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onPressEnter={submit}
          placeholder="描述故障，Enter 发送…"
          disabled={running || waiting}
          variant="borderless"
          style={{ background: '#0a0a0a', color: '#fafafa', flex: 1 }}
        />
        {running ? (
          <Button danger icon={<StopIcon />} onClick={onAbort}>
            停止
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={submit}
            style={{ background: '#fadb14', borderColor: '#fadb14', color: '#0a0a0a' }}
          >
            发送
          </Button>
        )}
      </div>
    </div>
  )
}

function StopIcon() {
  return <span style={{ width: 10, height: 10, background: '#ff4d4f', borderRadius: 2, display: 'inline-block' }} />
}

function Welcome({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div style={{ textAlign: 'center', padding: '64px 16px' }}>
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: '50%',
          background: 'rgba(250,219,20,0.12)',
          color: '#fadb14',
          fontSize: 34,
          margin: '0 auto 20px',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <RobotOutlined />
      </div>
      <div style={{ color: '#fafafa', fontSize: 18, fontWeight: 600, marginBottom: 8 }}>排查工作台</div>
      <div style={{ color: '#8c8c8c', fontSize: 13, marginBottom: 28 }}>
        描述工业机器人故障，AI 会逐步解析报警码 → 查询图谱 → 检索手册 → 生成排障 SOP
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 480, margin: '0 auto' }}>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            style={{
              background: '#0a0a0a',
              border: '1px solid #303030',
              borderRadius: 6,
              color: '#d9d9d9',
              padding: '10px 14px',
              cursor: 'pointer',
              fontSize: 13,
              textAlign: 'left',
              transition: 'border-color .2s, color .2s',
            }}
            onMouseEnter={(e) => ((e.target as HTMLElement).style.borderColor = 'rgba(250,219,20,0.5)')}
            onMouseLeave={(e) => ((e.target as HTMLElement).style.borderColor = '#303030')}
          >
            <ToolOutlined style={{ color: '#fadb14', marginRight: 8 }} />
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  return (
    <div style={{ display: 'flex', gap: 10, marginBottom: 18, justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      {!isUser && <Avatar color="rgba(250,219,20,0.15)" textColor="#fadb14" icon={<RobotOutlined />} />}
      <div style={{ maxWidth: '86%', minWidth: 0 }}>
        <PartsList parts={msg.parts} isUser={isUser} />
      </div>
      {isUser && <Avatar color="#2b2b2b" textColor="#d9d9d9" icon={<UserOutlined />} />}
    </div>
  )
}

function Avatar({ color, textColor, icon }: { color: string; textColor: string; icon: React.ReactNode }) {
  return (
    <span
      style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        background: color,
        color: textColor,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      {icon}
    </span>
  )
}

function Part({ part, isUser }: { part: Exclude<MessagePart, ToolPart>; isUser: boolean }) {
  if (part.kind === 'manual_images') {
    return <ImagesBlock images={part.images} />
  }
  if (part.kind === 'manual_chunks') {
    return <ChunksBlock chunks={part.chunks} />
  }
  if (part.kind === 'text') {
    if (isUser) {
      return (
        <div
          style={{
            background: '#2b2b2b',
            border: '1px solid #303030',
            borderRadius: 8,
            padding: '10px 14px',
            color: '#fafafa',
            fontSize: 13,
            lineHeight: 1.7,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {part.content}
        </div>
      )
    }
    return (
      <div
        style={{
          background: '#0a0a0a',
          border: '1px solid #303030',
          borderRadius: 8,
          padding: '10px 14px',
          color: '#fafafa',
          fontSize: 13,
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {part.content}
      </div>
    )
  }
  return <SopSummary sop={part.sop} />
}

/* ---------- 工具卡片分组：串行 vs 并行 ---------- */

/* ---------- 工具卡片分组：串行 vs 并行 ---------- */

const BRANCH_NODES = new Set(['run_subagent', 'direct_answer'])

/** 分支壳节点（run_subagent/direct_answer 的 start/end 卡片），不算「排查步骤」 */
function isWrapper(p: ToolPart): boolean {
  return BRANCH_NODES.has(p.node)
}

/** 一批连续工具卡片里出现的不同并行分支（无 branch 的卡片不算） */
function distinctBranches(parts: ToolPart[]): string[] {
  const s = new Set<string>()
  for (const p of parts) if (p.branch) s.add(p.branch)
  return [...s]
}

/** 连续工具卡片 → 分组：以「是否带并行分支」为界。
 *  外层流水线节点（意图/品牌/紧急度/分发）无 branch → 串行组；
 *  Send 分支内的节点带 branch → 归为一组，含 ≥2 个不同分支即并行。 */
function buildToolGroups(parts: ToolPart[]): ToolPart[][] {
  const groups: ToolPart[][] = []
  let cur: ToolPart[] = []
  let curBranchy = parts.length > 0 && parts[0].branch != null
  const flush = () => {
    if (cur.length) {
      groups.push(cur)
      cur = []
    }
  }
  for (const p of parts) {
    const branchy = p.branch != null
    if (branchy !== curBranchy) {
      flush()
      curBranchy = branchy
    }
    cur.push(p)
  }
  flush()
  return groups
}

/** 把整个消息的 parts 渲染出来：工具卡片成组，文本/SOP 原样 */
function PartsList({ parts, isUser }: { parts: MessagePart[]; isUser: boolean }) {
  const nodes: React.ReactNode[] = []
  let buf: ToolPart[] = []
  let textSeq = 0
  const flushTools = () => {
    if (!buf.length) return
    buildToolGroups(buf).forEach((g) => nodes.push(<ToolGroupView key={g[0].key} parts={g} />))
    buf = []
  }
  parts.forEach((p) => {
    if (p.kind === 'tool') {
      buf.push(p)
      return
    }
    flushTools()
    nodes.push(<Part key={p.kind === 'text' ? `t-${textSeq++}` : p.key} part={p} isUser={isUser} />)
  })
  flushTools()
  return <>{nodes}</>
}

function ToolGroupView({ parts }: { parts: ToolPart[] }) {
  return distinctBranches(parts).length >= 2 ? <ParallelGroup parts={parts} /> : <FlowBlock parts={parts} />
}

/** 串行卡片组：非分支壳节点按序编号 */
function SerialGroup({ parts }: { parts: ToolPart[] }) {
  let step = 0
  return (
    <>
      {parts.map((p) => {
        if (!isWrapper(p)) step += 1
        return <ToolCard key={p.key} part={p} step={isWrapper(p) ? null : step} />
      })}
    </>
  )
}

/** 分支流：含分支壳节点（run_subagent/direct_answer）时，子智能体内部步骤嵌套在父卡片下 */
function FlowBlock({ parts }: { parts: ToolPart[] }) {
  const parent = parts.find(isWrapper)
  if (!parent) return <SerialGroup parts={parts} />
  const siblings = parts.filter((p) => p.key !== parent.key)
  return (
    <div>
      <ToolCard part={parent} step={null} />
      {siblings.length > 0 && (
        <div className="subflow">
          <SerialGroup parts={siblings} />
        </div>
      )}
    </div>
  )
}

function ParallelGroup({ parts }: { parts: ToolPart[] }) {
  const byBranch = new Map<string, ToolPart[]>()
  for (const p of parts) {
    const k = p.branch ?? p.node
    if (!byBranch.has(k)) byBranch.set(k, [])
    byBranch.get(k)!.push(p)
  }
  return (
    <div className="parallel-frame">
      <div className="parallel-frame-head">
        <span className="parallel-badge">并行</span>
        <span style={{ color: '#8c8c8c', fontSize: 12 }}>以下分支同时执行</span>
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        {[...byBranch.entries()].map(([k, branchParts]) => {
          const name = branchParts.find((p) => p.branch_name)?.branch_name ?? k
          return (
            <div key={k} className="branch-column">
              <div className="branch-title">{name}</div>
              <FlowBlock parts={branchParts} />
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ToolCard({ part, step }: { part: ToolPart; step: number | null }) {
  const [expanded, setExpanded] = useState(false)
  const running = part.status === 'running'
  return (
    <div
      className={running ? 'tool-card tool-card-running' : 'tool-card tool-card-done'}
      style={{
        borderLeft: `3px solid ${running ? '#fadb14' : '#52c41a'}`,
        margin: '0 0 8px',
      }}
    >
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', cursor: 'pointer' }}
        onClick={() => running || setExpanded((v) => !v)}
      >
        {step != null && <span className="step-badge">{step}</span>}
        <ToolOutlined style={{ color: running ? '#fadb14' : '#52c41a' }} />
        <span style={{ color: '#fafafa', fontSize: 13, flex: 1 }}>{part.name}</span>
        {running ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#fadb14', fontSize: 12 }}>
            <LoadingOutlined />
            执行中
          </span>
        ) : (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#52c41a', fontSize: 12 }}>
            <CheckCircleFilled />
            完成
            {expanded ? <UpOutlined style={{ fontSize: 10 }} /> : <DownOutlined style={{ fontSize: 10 }} />}
          </span>
        )}
      </div>
      {expanded && (
        <pre
          style={{
            margin: 0,
            padding: '8px 12px',
            borderTop: '1px dashed #303030',
            background: '#0a0a0a',
            color: '#b7eb8f',
            fontSize: 11,
            lineHeight: 1.6,
            maxHeight: 260,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {JSON.stringify(part.result ?? {}, null, 2)}
        </pre>
      )}
    </div>
  )
}

/** 手册参考图块：检索召回的手册图片（OSS 签名 URL），点击可看大图。 */
function ImagesBlock({ images }: { images: ManualImage[] }) {
  return (
    <div
      style={{
        background: '#0a0a0a',
        border: '1px solid #303030',
        borderRadius: 8,
        padding: '10px 12px',
        margin: '0 0 8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <PictureOutlined style={{ color: '#fadb14' }} />
        <span style={{ color: '#fafafa', fontSize: 12, fontWeight: 600 }}>手册参考图</span>
        <span style={{ color: '#8c8c8c', fontSize: 11, marginLeft: 'auto' }}>{images.length} 张</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {images.map((img, i) => (
          <figure key={i} style={{ margin: 0, maxWidth: 220 }}>
            <Image
              src={img.asset_url}
              alt={img.content || '手册示意图'}
              width={220}
              style={{ borderRadius: 4, border: '1px solid #303030', background: '#141414' }}
              preview={{ mask: '查看大图' }}
            />
            <figcaption style={{ color: '#8c8c8c', fontSize: 11, lineHeight: 1.5, marginTop: 4 }}>
              {img.content}
              {img.page != null && ` · 第${img.page}页`}
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  )
}

/** 参考片段块：检索召回的手册文本，折叠展示（标题=章节·页码，展开看全文）。 */
function ChunksBlock({ chunks }: { chunks: ManualChunk[] }) {
  return (
    <div
      style={{
        background: '#0a0a0a',
        border: '1px solid #303030',
        borderRadius: 8,
        padding: '10px 12px',
        margin: '0 0 8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <FileTextOutlined style={{ color: '#fadb14' }} />
        <span style={{ color: '#fafafa', fontSize: 12, fontWeight: 600 }}>参考片段</span>
        <span style={{ color: '#8c8c8c', fontSize: 11, marginLeft: 'auto' }}>{chunks.length} 条</span>
      </div>
      <Collapse
        size="small"
        ghost
        items={chunks.map((c, i) => ({
          key: String(i),
          label: (
            <span style={{ color: '#fafafa', fontSize: 12 }}>
              {c.section || '手册片段'}
              {c.page != null ? ` · 第${c.page}页` : ''}
            </span>
          ),
          children: (
            <pre
              style={{
                margin: 0,
                color: '#d9d9d9',
                fontSize: 11,
                lineHeight: 1.7,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: 320,
                overflow: 'auto',
              }}
            >
              {c.content}
            </pre>
          ),
        }))}
      />
    </div>
  )
}

