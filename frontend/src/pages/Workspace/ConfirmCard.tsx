import { useState } from 'react'
import { Button, Input } from 'antd'
import { CheckCircleOutlined, LoadingOutlined } from '@ant-design/icons'
import SopSummary from './SopSummary'
import type { ConfirmEvent } from './types'

interface Props {
  confirm: Omit<ConfirmEvent, 'type'> | null
  busy?: boolean
  onDecision: (input: string) => void
}

/** 人工确认浮层：先展示已生成的 SOP（可滑动审阅），再让用户选择/备注后 resume 续跑。 */
export default function ConfirmCard({ confirm, busy, onDecision }: Props) {
  const [remark, setRemark] = useState('')
  if (!confirm) return null
  const { prompt, options = [], sops = [] } = confirm

  return (
    <div
      style={{
        border: '1px solid rgba(250,173,20,0.6)',
        background: 'rgba(250,173,20,0.08)',
        borderRadius: 8,
        padding: '12px 14px',
        margin: '0 0 10px',
      }}
    >
      {sops.length > 0 && (
        <div
          style={{
            maxHeight: 300,
            overflow: 'auto',
            marginBottom: 10,
            border: '1px solid rgba(250,219,20,0.35)',
            borderRadius: 6,
            padding: '4px 4px 0',
            background: 'rgba(10,10,10,0.4)',
          }}
        >
          <div style={{ color: '#fadb14', fontSize: 12, fontWeight: 600, padding: '8px 8px 0' }}>
            已生成排障 SOP（{sops.length} 个分支，可滑动查看）
          </div>
          <div style={{ padding: 8 }}>
            {sops.map((sop, i) => (
              <SopSummary key={i} sop={sop} />
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '1px 8px',
            borderRadius: 4,
            background: 'rgba(250,173,20,0.18)',
            color: '#faad14',
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          <CheckCircleOutlined />
          需要确认
        </span>
        <span style={{ color: '#fafafa', fontSize: 13, flex: 1 }}>{prompt}</span>
      </div>

      {options.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
          {options.map((opt) => (
            <Button
              key={opt}
              size="small"
              disabled={busy}
              onClick={() => onDecision(opt)}
              style={{ color: '#fafafa', borderColor: 'rgba(250,219,20,0.5)' }}
            >
              {opt}
            </Button>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <Input
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
          placeholder="备注 / 自定义指令（可选）"
          variant="borderless"
          disabled={busy}
          onPressEnter={() => remark.trim() && onDecision(remark.trim())}
          style={{ background: '#0a0a0a', color: '#fafafa', flex: 1 }}
        />
        <Button
          type="primary"
          size="small"
          disabled={busy || !remark.trim()}
          icon={busy ? <LoadingOutlined /> : undefined}
          onClick={() => onDecision(remark.trim())}
          style={{ background: '#fadb14', borderColor: '#fadb14', color: '#0a0a0a' }}
        >
          {busy ? '续跑中…' : '提交'}
        </Button>
      </div>
    </div>
  )
}
