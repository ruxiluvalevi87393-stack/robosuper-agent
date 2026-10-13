import { Button, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useChatSse } from '../../hooks/useChatSse'
import ChatPanel from './ChatPanel'
import GraphPanel from './GraphPanel'

const STATUS_MAP: Record<string, { text: string; color: string }> = {
  idle: { text: '待命', color: 'default' },
  running: { text: '排查中…', color: 'gold' },
  waiting: { text: '待确认', color: 'orange' },
  done: { text: '已完成', color: 'green' },
  error: { text: '出错', color: 'red' },
}

/** 工程师排查桌面工作台：对话（工具卡片/确认卡）｜图谱诊断（F3）两栏。 */
export default function Workspace() {
  const { messages, status, error, confirm, graphs, send, confirmDecision, abort, reset } = useChatSse()
  const st = STATUS_MAP[status]

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="page-header" style={{ marginBottom: 0 }}>
        <h2>排查工作台</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {error && <Tag color="red">{error}</Tag>}
          <Tag color={st.color}>{st.text}</Tag>
          <Button icon={<PlusOutlined />} onClick={reset} size="small">
            新会话
          </Button>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <ChatPanel
            messages={messages}
            status={status}
            confirm={confirm}
            onConfirm={confirmDecision}
            onSend={send}
            onAbort={abort}
          />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <GraphPanel graphs={graphs} />
        </div>
      </div>
    </div>
  )
}
